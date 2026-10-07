from __future__ import annotations

import sys

from app.config import AppConfig, ConfigurationError


def main() -> int:
    print("SANA GPS starting...")

    try:
        config = AppConfig.from_env()
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    print("Configuration loaded")
    print("Host:", config.host)
    print("Port:", config.port)
    print("Log level:", config.log_level)
    print("SANA GPS ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
