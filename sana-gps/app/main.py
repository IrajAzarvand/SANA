from __future__ import annotations

import asyncio
import signal
import sys

from app.config import AppConfig, ConfigurationError
from app.database.pool import DatabaseConnectionPool
from app.transport.server import TransportServer
from app.transport.session import SessionManager


async def run(
    config: AppConfig,
    shutdown_event: asyncio.Event | None = None,
) -> int:
    """Run the GPS runtime until shutdown is requested."""

    if config.database is None:
        print("Database configuration is missing", file=sys.stderr)
        return 2

    database_pool = DatabaseConnectionPool(config.database)
    session_manager = SessionManager()

    async def on_data(session, data: bytes) -> None:
        # Protocol handling starts in Stage 4.
        return None

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
        print("PostgreSQL pool initialized")
        print("Database connection OK")

        await transport_server.start()

        print("Host:", config.host)
        print("TCP port:", config.tcp_port)
        print("UDP port:", config.udp_port)
        print("Log level:", config.log_level)
        print("SANA GPS ready")

        if shutdown_event is None:
            shutdown_event = asyncio.Event()

        await shutdown_event.wait()
        return 0
    except Exception as exc:
        print(f"SANA GPS runtime error: {exc}", file=sys.stderr)
        return 3
    finally:
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

    print("Configuration loaded")

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
