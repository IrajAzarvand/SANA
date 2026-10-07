from __future__ import annotations

import os
from dataclasses import dataclass


_ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


class ConfigurationError(ValueError):
    """Raised when SANA GPS runtime configuration is invalid."""


@dataclass(frozen=True, slots=True)
class AppConfig:
    host: str = "0.0.0.0"
    port: int = 9000
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "AppConfig":
        host = os.getenv("SANA_GPS_HOST", cls.host).strip()
        if not host:
            raise ConfigurationError("SANA_GPS_HOST must not be empty")

        raw_port = os.getenv("SANA_GPS_PORT", str(cls.port)).strip()
        try:
            port = int(raw_port)
        except ValueError as exc:
            raise ConfigurationError(
                "SANA_GPS_PORT must be an integer"
            ) from exc

        if not 1 <= port <= 65535:
            raise ConfigurationError(
                "SANA_GPS_PORT must be between 1 and 65535"
            )

        log_level = os.getenv("SANA_GPS_LOG_LEVEL", cls.log_level).strip().upper()
        if log_level not in _ALLOWED_LOG_LEVELS:
            allowed = ", ".join(sorted(_ALLOWED_LOG_LEVELS))
            raise ConfigurationError(
                f"SANA_GPS_LOG_LEVEL must be one of: {allowed}"
            )

        return cls(host=host, port=port, log_level=log_level)
