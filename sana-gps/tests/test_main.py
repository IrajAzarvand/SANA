import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.config import AppConfig, DatabaseConfig
from app.main import run


@pytest.mark.asyncio
async def test_run_starts_runtime_and_shuts_down_cleanly():
    config = AppConfig(
        host="127.0.0.1",
        tcp_port=9000,
        udp_port=9001,
        log_level="INFO",
        database=DatabaseConfig(
            name="sana_db",
            user="sana_user",
            password="secret",
        ),
    )
    shutdown_event = asyncio.Event()
    shutdown_event.set()

    database_pool = Mock()
    transport_server = Mock()
    transport_server.start = AsyncMock()
    transport_server.stop = AsyncMock()

    with (
        patch("app.main.DatabaseConnectionPool", return_value=database_pool),
        patch("app.main.TransportServer", return_value=transport_server),
    ):
        result = await run(config, shutdown_event)

    assert result == 0
    database_pool.open.assert_called_once()
    database_pool.close.assert_called_once()
    transport_server.start.assert_awaited_once()
    transport_server.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_rejects_missing_database_configuration():
    config = AppConfig(
        host="127.0.0.1",
        tcp_port=9000,
        udp_port=9001,
        log_level="INFO",
        database=None,
    )

    result = await run(config, asyncio.Event())

    assert result == 2
