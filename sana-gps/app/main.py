from __future__ import annotations

import sys

from app.config import AppConfig, ConfigurationError
from app.database.pool import DatabaseConnectionPool


def main() -> int:
    print("SANA GPS starting...")

    try:
        config = AppConfig.from_env()
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    print("Configuration loaded")

    database_pool = DatabaseConnectionPool(config.database)
    try:
        database_pool.open()
    except Exception as exc:
        print(f"Database connection error: {exc}", file=sys.stderr)
        return 3

    print("PostgreSQL pool initialized")
    print("Database connection OK")
    print("Host:", config.host)
    print("Port:", config.port)
    print("Log level:", config.log_level)
    print("SANA GPS ready")

    database_pool.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
