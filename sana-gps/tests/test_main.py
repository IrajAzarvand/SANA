import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.config import AppConfig, DatabaseConfig
from app.main import configure_logging, run


@pytest.mark.asyncio
async def test_run_starts_traccar_and_map_matching_workers_without_sana_listeners():
    config = AppConfig(
        log_level="INFO",
        database=DatabaseConfig(name="sana_db", user="sana_user", password="secret"),
    )
    shutdown_event = asyncio.Event()
    shutdown_event.set()
    database_pool = Mock()

    with (
        patch("app.main.DatabaseConnectionPool", return_value=database_pool),
        patch("app.main.run_map_matching_worker", new_callable=AsyncMock),
    ):
        result = await run(config, shutdown_event)

    assert result == 0
    database_pool.open.assert_called_once()
    database_pool.close.assert_called_once()


@pytest.mark.asyncio
async def test_run_rejects_missing_database_configuration():
    config = AppConfig(database=None)
    assert await run(config, asyncio.Event()) == 2


def test_configure_logging_uses_requested_level_and_stdout():
    with patch("app.main.logging.basicConfig") as basic_config:
        configure_logging("DEBUG")
    kwargs = basic_config.call_args.kwargs
    assert kwargs["level"] == 10
    assert kwargs["stream"] is not None
    assert kwargs["force"] is True
    assert "%(levelname)s" in kwargs["format"]
