from __future__ import annotations

import math
import os
from dataclasses import dataclass


_DEFAULT_LOG_LEVEL = "INFO"
_ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}
_DEFAULT_DB_HOST = "127.0.0.1"
_DEFAULT_DB_PORT = 5432
_DEFAULT_DB_POOL_MIN = 2
_DEFAULT_DB_POOL_MAX = 10


class ConfigurationError(ValueError):
    """Raised when SANA GPS runtime configuration is invalid."""


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    host: str = _DEFAULT_DB_HOST
    port: int = _DEFAULT_DB_PORT
    name: str = ""
    user: str = ""
    password: str = ""
    pool_min_size: int = _DEFAULT_DB_POOL_MIN
    pool_max_size: int = _DEFAULT_DB_POOL_MAX

    @property
    def conninfo(self) -> str:
        from psycopg.conninfo import make_conninfo
        return make_conninfo(host=self.host, port=self.port, dbname=self.name, user=self.user, password=self.password)

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        host = os.getenv("SANA_GPS_DB_HOST", _DEFAULT_DB_HOST).strip()
        if not host:
            raise ConfigurationError("SANA_GPS_DB_HOST must not be empty")
        port = _parse_int_env("SANA_GPS_DB_PORT", _DEFAULT_DB_PORT, minimum=1, maximum=65535)
        name = os.getenv("SANA_GPS_DB_NAME", "").strip()
        user = os.getenv("SANA_GPS_DB_USER", "sana_user").strip()
        password = os.getenv("SANA_GPS_DB_PASSWORD", os.getenv("DB_PASSWORD", "sana_password_123"))
        if not name:
            raise ConfigurationError("SANA_GPS_DB_NAME must not be empty")
        if not user:
            raise ConfigurationError("SANA_GPS_DB_USER must not be empty")
        if user != "sana_user":
            raise ConfigurationError("SANA_GPS_DB_USER must be 'sana_user'")
        if not password:
            raise ConfigurationError("SANA_GPS_DB_PASSWORD must not be empty")
        pool_min_size = _parse_int_env("SANA_GPS_DB_POOL_MIN", _DEFAULT_DB_POOL_MIN, minimum=1)
        pool_max_size = _parse_int_env("SANA_GPS_DB_POOL_MAX", _DEFAULT_DB_POOL_MAX, minimum=1)
        if pool_min_size > pool_max_size:
            raise ConfigurationError("SANA_GPS_DB_POOL_MIN must not exceed SANA_GPS_DB_POOL_MAX")
        return cls(host=host, port=port, name=name, user=user, password=password,
                   pool_min_size=pool_min_size, pool_max_size=pool_max_size)


@dataclass(frozen=True, slots=True)
class AppConfig:
    log_level: str = _DEFAULT_LOG_LEVEL
    database: DatabaseConfig | None = None
    neshan_map_matching_api_key: str | None = None
    traccar_api_url: str = "http://127.0.0.1:8082/api"
    traccar_api_username: str = ""
    traccar_api_password: str = ""
    traccar_sync_interval: float = 60.0

    @classmethod
    def from_env(cls) -> "AppConfig":
        neshan_key = os.getenv("NESHAN_MAP_MATCHING_API_KEY", "").strip() or None
        traccar_api_url = os.getenv("SANA_GPS_TRACCAR_API_URL", "http://127.0.0.1:8082/api").strip().rstrip("/")
        traccar_username = os.getenv("SANA_GPS_TRACCAR_API_USERNAME", "").strip()
        traccar_password = os.getenv("SANA_GPS_TRACCAR_API_PASSWORD", "")
        if bool(traccar_username) != bool(traccar_password):
            raise ConfigurationError("SANA_GPS_TRACCAR_API_USERNAME and SANA_GPS_TRACCAR_API_PASSWORD must be set together")
        sync_interval = _parse_float_env("SANA_GPS_TRACCAR_SYNC_INTERVAL", 60.0, minimum=5.0)
        log_level = os.getenv("SANA_GPS_LOG_LEVEL", _DEFAULT_LOG_LEVEL).strip().upper()
        if log_level not in _ALLOWED_LOG_LEVELS:
            allowed = ", ".join(sorted(_ALLOWED_LOG_LEVELS))
            raise ConfigurationError(f"SANA_GPS_LOG_LEVEL must be one of: {allowed}")
        return cls(log_level=log_level, database=DatabaseConfig.from_env(),
                   neshan_map_matching_api_key=neshan_key, traccar_api_url=traccar_api_url,
                   traccar_api_username=traccar_username, traccar_api_password=traccar_password,
                   traccar_sync_interval=sync_interval)


def _parse_float_env(name: str, default: float, *, minimum: float | None = None) -> float:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number") from exc
    if not math.isfinite(value):
        raise ConfigurationError(f"{name} must be a finite number")
    if minimum is not None and value < minimum:
        raise ConfigurationError(f"{name} must be at least {minimum}")
    return value


def _parse_int_env(name: str, default: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if minimum is not None and value < minimum:
        raise ConfigurationError(f"{name} must be at least {minimum}")
    if maximum is not None and value > maximum:
        raise ConfigurationError(f"{name} must be at most {maximum}")
    return value
