from __future__ import annotations

import asyncio
import logging
import signal
import sys

from app.config import AppConfig, ConfigurationError
from app.database.pool import DatabaseConnectionPool
from app.diagnostics.capture import RawCapture
from app.protocols.dispatcher import ProtocolDispatcher
from app.protocols.gt06_handler import GT06Handler
from app.protocols.hq_handler import HQHandler
from app.protocols.teltonika.handler import TeltonikaHandler
from app.protocols.types import ProtocolId, ProtocolResponse
from app.repositories.device import DeviceRepository
from app.repositories.unknown_protocol_queue import UnknownProtocolQueueRepository
from app.repositories.gt06_position import GT06PositionRepository
from app.repositories.gps_telemetry import GPSTelemetryRepository
from app.processing.map_matching import run_map_matching_worker
from app.transport.server import TransportServer
from app.transport.session import SessionManager, TransportType
from app.traccar.client import TraccarClient
from app.traccar.device_sync import run_device_sync_worker, sync_devices_once
from app.traccar.pending_repository import TraccarPendingDeviceRepository
from app.traccar.position_receiver import TraccarPositionReceiver
from app.traccar.webhook_server import TraccarWebhookServer


_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_UNKNOWN_QUEUE_POLL_SECONDS = 5.0
logger = logging.getLogger(__name__)


async def _monitor_unknown_protocol_queue(
    shutdown_event: asyncio.Event,
    device_repository: DeviceRepository,
    queue_repository: UnknownProtocolQueueRepository,
) -> None:
    """Re-check the durable queue periodically, including after new device registration.

    Polling avoids requiring a GPS-service restart or database trigger permissions.
    New registrations and new unknown packets are picked up within the poll interval.
    """
    while not shutdown_event.is_set():
        try:
            identifiers = await asyncio.to_thread(device_repository.find_all_identifiers)
            matched = await asyncio.to_thread(
                queue_repository.match_pending_sessions, identifiers
            )
            if matched:
                logger.info("Matched %d unknown GPS session(s) to registered device(s)", matched)
        except Exception:
            logger.exception("Unknown GPS queue scan failed; it will retry")
        try:
            await asyncio.wait_for(
                shutdown_event.wait(), timeout=_UNKNOWN_QUEUE_POLL_SECONDS
            )
        except asyncio.TimeoutError:
            pass


def configure_logging(level: str) -> None:
    """Configure root logging so application events reach systemd journal."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=_LOG_FORMAT,
        stream=sys.stdout,
        force=True,
    )


async def run(
    config: AppConfig,
    shutdown_event: asyncio.Event | None = None,
) -> int:
    """Run the GPS runtime until shutdown is requested."""

    if config.database is None:
        print("Database configuration is missing", file=sys.stderr)
        return 2
    if shutdown_event is None:
        shutdown_event = asyncio.Event()

    database_pool = DatabaseConnectionPool(config.database)
    session_manager = SessionManager()
    device_repository = DeviceRepository(database_pool)
    telemetry_repository = GPSTelemetryRepository(database_pool)
    teltonika_handler = TeltonikaHandler(
        device_repository, telemetry_repository, session_manager=session_manager
    )
    gt06_handler = GT06Handler(
        device_repository,
        GT06PositionRepository(database_pool),
        session_manager=session_manager,
    )
    hq_handler = HQHandler(
        device_repository, telemetry_repository, session_manager=session_manager
    )
    capture = RawCapture(config.capture_file) if config.capture_file else None
    gt06_capture = RawCapture(config.gt06_capture_file) if config.gt06_capture_file else None
    unknown_queue_repository = UnknownProtocolQueueRepository(database_pool)
    queue_task: asyncio.Task[None] | None = None
    map_matching_task: asyncio.Task[None] | None = None
    traccar_sync_task: asyncio.Task[None] | None = None
    traccar_webhook: TraccarWebhookServer | None = None

    async def on_gt06_data(session, data: bytes) -> ProtocolResponse | None:
        if gt06_capture is not None:
            gt06_capture.write(
                transport=session.transport.value,
                remote=session.remote_address,
                data=data,
            )
        return await gt06_handler.handle(session, data)

    def on_unknown_data(session, data: bytes) -> None:
        # Persist before returning from the transport callback so a process restart
        # cannot erase an already received unknown-protocol chunk.
        unknown_queue_repository.record_chunk(
            session_id=session.id,
            remote_address=session.remote_address,
            transport=session.transport.value,
            payload=data,
        )

    dispatcher = ProtocolDispatcher(
        {
            ProtocolId.TELTONIKA: teltonika_handler.handle,
            ProtocolId.GT06: on_gt06_data,
            ProtocolId.HQ: hq_handler.handle,
        },
        unknown_data_handler=on_unknown_data,
    )

    async def on_data(session, data: bytes) -> ProtocolResponse | None:
        if capture is not None:
            capture.write(
                transport=session.transport.value,
                remote=session.remote_address,
                data=data,
            )
        # The shared signature-based dispatcher is for TCP streams. Teltonika's
        # UDP framing is different, so preserve its dedicated legacy UDP path.
        if session.transport is TransportType.UDP:
            return await teltonika_handler.handle(session, data)
        return await dispatcher.handle(session, data)

    transport_server = TransportServer(
        config.host,
        config.tcp_port,
        config.udp_port,
        session_manager,
        on_data,
        tcp_idle_timeout=config.tcp_idle_timeout,
        udp_session_timeout=config.udp_session_timeout,
        max_tcp_connections=config.max_tcp_connections,
        max_udp_sessions=config.max_udp_sessions,
        max_datagram_size=config.max_datagram_size,
    )

    try:
        database_pool.open()
        unknown_queue_repository.check_schema()
        pending_traccar_repository = TraccarPendingDeviceRepository(database_pool)
        pending_schema_available = pending_traccar_repository.check_schema()
        if not pending_schema_available:
            logger.warning(
                "Traccar unknown-device staging is unavailable until SQL migration "
                "0009 is applied; existing GPS listeners will continue"
            )
        print("PostgreSQL pool initialized")
        print("Database connection OK")

        # Traccar integration is additive: existing TCP/UDP ingestion remains
        # active. Credentials enable immediate and recurring device reconciliation.
        traccar_client: TraccarClient | None = None
        if config.traccar_api_username and config.traccar_api_password:
            traccar_client = TraccarClient(
                api_url=config.traccar_api_url,
                username=config.traccar_api_username,
                password=config.traccar_api_password,
            )
            try:
                created = await asyncio.to_thread(
                    sync_devices_once,
                    traccar_client,
                    device_repository,
                    pending_traccar_repository,
                )
                logger.info("Traccar startup reconciliation complete; created=%d", created)
            except Exception:
                logger.exception(
                    "Initial Traccar synchronization failed; periodic retry will continue"
                )
            traccar_sync_task = asyncio.create_task(
                run_device_sync_worker(
                    shutdown_event,
                    traccar_client,
                    device_repository,
                    pending_traccar_repository,
                    interval_seconds=config.traccar_sync_interval,
                ),
                name="sana-traccar-device-sync",
            )
        else:
            logger.warning(
                "Traccar device sync disabled: set SANA_GPS_TRACCAR_API_USERNAME "
                "and SANA_GPS_TRACCAR_API_PASSWORD in the service environment"
            )

        if config.traccar_webhook_secret:
            if traccar_client is None:
                logger.warning(
                    "Traccar position webhook is not started because Traccar API credentials are missing"
                )
            else:
                position_receiver = TraccarPositionReceiver(
                    client=traccar_client,
                    device_repository=device_repository,
                    telemetry_repository=telemetry_repository,
                )
                traccar_webhook = TraccarWebhookServer(
                    host=config.traccar_webhook_host,
                    port=config.traccar_webhook_port,
                    secret=config.traccar_webhook_secret,
                    receiver=position_receiver,
                )
                await traccar_webhook.start()
                logger.info(
                    "Traccar webhook listening on %s:%d",
                    config.traccar_webhook_host,
                    config.traccar_webhook_port,
                )
        else:
            logger.warning(
                "Traccar position webhook disabled: SANA_GPS_TRACCAR_WEBHOOK_SECRET is not set"
            )

        await transport_server.start()

        print("Host:", config.host)
        print("Shared TCP port:", config.tcp_port)
        print("UDP port:", config.udp_port)
        print("Log level:", config.log_level)
        if capture is not None:
            print("Raw capture:", capture.path)
        if gt06_capture is not None:
            print("GT06 raw capture:", gt06_capture.path)
        print("Unknown protocol queue: PostgreSQL durable storage; device scan every 5 seconds")
        print("Traccar integration: startup reconciliation plus periodic sync when credentials are configured")
        print("SANA GPS ready")

        queue_task = asyncio.create_task(
            _monitor_unknown_protocol_queue(
                shutdown_event, device_repository, unknown_queue_repository
            ),
            name="sana-unknown-gps-queue-monitor",
        )
        map_matching_task = asyncio.create_task(
            run_map_matching_worker(
                shutdown_event,
                database_pool,
                config.neshan_map_matching_api_key,
            ),
            name="sana-neshan-map-matching-worker",
        )
        await shutdown_event.wait()
        return 0
    except Exception as exc:
        print(f"SANA GPS runtime error: {exc}", file=sys.stderr)
        return 3
    finally:
        tasks = [
            task for task in (queue_task, map_matching_task, traccar_sync_task)
            if task is not None
        ]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if traccar_webhook is not None:
            await traccar_webhook.stop()
        try:
            await transport_server.stop()
        finally:
            session_manager.close_all()
            session_manager.clear_closed()
            database_pool.close()


def _install_signal_handlers(
    loop: asyncio.AbstractEventLoop,
    shutdown_event: asyncio.Event,
) -> list[signal.Signals]:
    installed: list[signal.Signals] = []

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, shutdown_event.set)
            installed.append(sig)
        except (NotImplementedError, RuntimeError):
            signal.signal(sig, lambda *_args: shutdown_event.set())
            installed.append(sig)

    return installed


def _remove_signal_handlers(
    loop: asyncio.AbstractEventLoop,
    installed: list[signal.Signals],
) -> None:
    for sig in installed:
        try:
            loop.remove_signal_handler(sig)
        except (NotImplementedError, RuntimeError):
            pass


def main() -> int:
    print("SANA GPS starting...")

    try:
        config = AppConfig.from_env()
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    configure_logging(config.log_level)
    logging.getLogger(__name__).info("Configuration loaded; log level=%s", config.log_level)

    async def runner() -> int:
        shutdown_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        installed = _install_signal_handlers(loop, shutdown_event)
        try:
            return await run(config, shutdown_event)
        finally:
            _remove_signal_handlers(loop, installed)

    return asyncio.run(runner())


if __name__ == "__main__":
    raise SystemExit(main())
