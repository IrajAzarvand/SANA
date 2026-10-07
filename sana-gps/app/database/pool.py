from __future__ import annotations

from psycopg_pool import ConnectionPool

from app.config import DatabaseConfig


class DatabaseConnectionPool:
    """Owns the application's PostgreSQL connection pool lifecycle."""

    def __init__(self, config: DatabaseConfig) -> None:
        self._pool = ConnectionPool(
            conninfo=config.conninfo,
            min_size=config.pool_min_size,
            max_size=config.pool_max_size,
            open=False,
        )

    def open(self) -> None:
        self._pool.open(wait=True)
        try:
            with self._pool.connection() as connection:
                connection.execute("SELECT 1")
        except Exception:
            self._pool.close()
            raise

    def close(self) -> None:
        self._pool.close()

    def check(self) -> None:
        with self._pool.connection() as connection:
            connection.execute("SELECT 1")
