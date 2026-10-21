from __future__ import annotations

import asyncio
import logging
import signal
import sys

from app.config import AppConfig, ConfigurationError
from app.database.pool import DatabaseConnectionPool
from app.processing.map_matching import run_map_matching_worker
from app.repositories.device import DeviceRepository
from app.traccar.client import TraccarClient
from app.traccar.device_sync import run_device_sync_worker, sync_devices_once

logger = logging.getLogger(__name__)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        stream=sys.stdout,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )


async def run(
    config: AppConfig,
    shutdown_event: asyncio.Event | None = None,
) -> int:
    """Run Traccar integration and on-demand map matching only.

    Device TCP/UDP telemetry is received by Traccar. SANA intentionally does not
    run its legacy protocol listeners or accept Traccar position webhooks.
    """
    if config.database is None:
        print("Database configuration is missing", file=sys.stderr)
        return 2
    if shutdown_event is None:
        shutdown_event = asyncio.Event()

    pool = DatabaseConnectionPool(config.database)
    sync_task: asyncio.Task[None] | None = None
    matching_task: asyncio.Task[None] | None = None
    try:
        pool.open()
        devices = DeviceRepository(pool)
        client = None
        if config.traccar_api_username and config.traccar_api_password:
            client = TraccarClient(
                api_url=config.traccar_api_url,
                username=config.traccar_api_username,
                password=config.traccar_api_password,
            )
            try:
                created = await asyncio.to_thread(sync_devices_once, client, devices)
                logger.info("Traccar reconciliation complete; created=%d", created)
            except Exception:
                logger.exception("Initial Traccar reconciliation failed; periodic retry will continue")
            sync_task = asyncio.create_task(
                run_device_sync_worker(
                    shutdown_event, client, devices,
                    interval_seconds=config.traccar_sync_interval,
                ),
                name="sana-traccar-device-sync",
            )
        else:
            logger.warning(
                "Traccar integration is disabled: set SANA_GPS_TRACCAR_API_USERNAME "
                "and SANA_GPS_TRACCAR_API_PASSWORD"
            )

        matching_task = asyncio.create_task(
            run_map_matching_worker(
                shutdown_event,
                pool,
                config.neshan_map_matching_api_key,
                client,
            ),
            name="sana-neshan-map-matching-worker",
        )
        print("PostgreSQL pool initialized")
        print("GPS source of truth: Traccar")
        print("SANA raw TCP/UDP listeners: disabled")
        print("Traccar position webhook: disabled; raw positions are not copied to SANA")
        print("Neshan matching: runs only while a map watcher is active")
        print("SANA GPS ready")
        await shutdown_event.wait()
        return 0
    except Exception as exc:
        logger.exception("SANA GPS runtime failed")
        print(f"SANA GPS runtime error: {exc}", file=sys.stderr)
        return 3
    finally:
        tasks = [task for task in (sync_task, matching_task) if task is not None]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        pool.close()


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
    logger.info("Configuration loaded; log level=%s", config.log_level)

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
