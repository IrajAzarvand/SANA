from __future__ import annotations

from unittest.mock import Mock

from app.database.pool import DatabaseConnectionPool


def test_connection_configuration_sets_tehran_timezone() -> None:
    connection = Mock()

    DatabaseConnectionPool._configure_connection(connection)

    connection.execute.assert_called_once_with("SET TIME ZONE 'Asia/Tehran'")
