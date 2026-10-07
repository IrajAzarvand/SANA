from __future__ import annotations

import os
from dataclasses import dataclass


_DEFAULT_HOST = "0.0.0.0"
_DEFAULT_PORT = 9000
_DEFAULT_LOG_LEVEL = "INFO"
_ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


class ConfigurationError(ValueError):
    """Raised when SANA GPS runtime configuration is invalid."""


@dataclass(frozen=True, slots=True)
class AppConfig:
    host: str = _DEFAULT_HOST
    port: int = _DEFAULT_PORT
    log_level: str = _DEFAULT_LOG_LEVEL

    @classmethod
    def from_env(cls) -> "AppConfig":
        host = os.getenv("SANA_GPS_HOST", _DEFAULT_HOST).strip()
        if not host:
            raise ConfigurationError("SANA_GPS_HOST must not be empty")

        raw_port = os.getenv("SANA_GPS_PORT", str(_DEFAULT_PORT)).strip()
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

        log_level = os.getenv(
            "SANA_GPS_LOG_LEVEL", _DEFAULT_LOG_LEVEL
        ).strip().upper()
        if log_level not in _ALLOWED_LOG_LEVELS:
            allowed = ", ".join(sorted(_ALLOWED_LOG_LEVELS))
            raise ConfigurationError(
                f"SANA_GPS_LOG_LEVEL must be one of: {allowed}"
            )

        return cls(host=host, port=port, log_level=log_level)
