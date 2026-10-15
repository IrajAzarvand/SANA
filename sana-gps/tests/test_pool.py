import unittest
from unittest.mock import MagicMock, patch

from app.config import DatabaseConfig
from app.database.pool import DatabaseConnectionPool


class DatabaseConnectionPoolTests(unittest.TestCase):
    @patch("app.database.pool.ConnectionPool")
    def test_open_validates_connection(self, pool_class):
        pool = pool_class.return_value
        connection = MagicMock()
        pool.connection.return_value.__enter__.return_value = connection

        config = DatabaseConfig(
            name="sana_db",
            user="sana_user",
            password="secret",
        )
        database_pool = DatabaseConnectionPool(config)

        database_pool.open()

        pool.open.assert_called_once_with(wait=True)
        connection.execute.assert_called_once_with("SELECT 1")

    @patch("app.database.pool.ConnectionPool")
    def test_open_closes_pool_when_validation_fails(self, pool_class):
        pool = pool_class.return_value
        connection = MagicMock()
        connection.execute.side_effect = RuntimeError("database unavailable")
        pool.connection.return_value.__enter__.return_value = connection

        config = DatabaseConfig(
            name="sana_db",
            user="sana_user",
            password="secret",
        )
        database_pool = DatabaseConnectionPool(config)

        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            database_pool.open()

        pool.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
