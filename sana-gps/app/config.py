from __future__ import annotations

import math
import os
from dataclasses import dataclass


_DEFAULT_HOST = "0.0.0.0"
_DEFAULT_TCP_PORT = 9000
_DEFAULT_UDP_PORT = 9001
_DEFAULT_LOG_LEVEL = "INFO"
_DEFAULT_TCP_IDLE_TIMEOUT = 300.0
_DEFAULT_UDP_SESSION_TIMEOUT = 300.0
_DEFAULT_MAX_TCP_CONNECTIONS = 100
_DEFAULT_MAX_UDP_SESSIONS = 10000
_DEFAULT_MAX_DATAGRAM_SIZE = 8192
_ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}

_DEFAULT_DB_HOST = "127.0.0.1"
_DEFAULT_DB_PORT = 5432
_DEFAULT_DB_POOL_MIN = 1
_DEFAULT_DB_POOL_MAX = 5


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

        return make_conninfo(
            host=self.host,
            port=self.port,
            dbname=self.name,
            user=self.user,
            password=self.password,
        )

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        host = os.getenv("SANA_GPS_DB_HOST", _DEFAULT_DB_HOST).strip()
        if not host:
            raise ConfigurationError("SANA_GPS_DB_HOST must not be empty")

        port = _parse_int_env(
            "SANA_GPS_DB_PORT", _DEFAULT_DB_PORT, minimum=1, maximum=65535
        )
        name = os.getenv("SANA_GPS_DB_NAME", "").strip()
        user = os.getenv("SANA_GPS_DB_USER", "").strip()
        password = os.getenv("SANA_GPS_DB_PASSWORD", "")

        if not name:
            raise ConfigurationError("SANA_GPS_DB_NAME must not be empty")
        if not user:
            raise ConfigurationError("SANA_GPS_DB_USER must not be empty")
        if not password:
            raise ConfigurationError("SANA_GPS_DB_PASSWORD must not be empty")

        pool_min_size = _parse_int_env(
            "SANA_GPS_DB_POOL_MIN", _DEFAULT_DB_POOL_MIN, minimum=1
        )
        pool_max_size = _parse_int_env(
            "SANA_GPS_DB_POOL_MAX", _DEFAULT_DB_POOL_MAX, minimum=1
        )
        if pool_min_size > pool_max_size:
            raise ConfigurationError(
                "SANA_GPS_DB_POOL_MIN must not exceed SANA_GPS_DB_POOL_MAX"
            )

        return cls(
            host=host,
            port=port,
            name=name,
            user=user,
            password=password,
            pool_min_size=pool_min_size,
            pool_max_size=pool_max_size,
        )


@dataclass(frozen=True, slots=True)
class AppConfig:
    host: str = _DEFAULT_HOST
    tcp_port: int = _DEFAULT_TCP_PORT
    udp_port: int = _DEFAULT_UDP_PORT
    log_level: str = _DEFAULT_LOG_LEVEL
    tcp_idle_timeout: float = _DEFAULT_TCP_IDLE_TIMEOUT
    udp_session_timeout: float = _DEFAULT_UDP_SESSION_TIMEOUT
    max_tcp_connections: int = _DEFAULT_MAX_TCP_CONNECTIONS
    max_udp_sessions: int = _DEFAULT_MAX_UDP_SESSIONS
    max_datagram_size: int = _DEFAULT_MAX_DATAGRAM_SIZE
    capture_file: str | None = None
    database: DatabaseConfig | None = None

    @classmethod
    def from_env(cls) -> "AppConfig":
        host = os.getenv("SANA_GPS_HOST", _DEFAULT_HOST).strip()
        if not host:
            raise ConfigurationError("SANA_GPS_HOST must not be empty")

        tcp_port = _parse_int_env(
            "SANA_GPS_TCP_PORT", _DEFAULT_TCP_PORT, minimum=1, maximum=65535
        )
        udp_port = _parse_int_env(
            "SANA_GPS_UDP_PORT", _DEFAULT_UDP_PORT, minimum=1, maximum=65535
        )

        tcp_idle_timeout = _parse_float_env(
            "SANA_GPS_TCP_IDLE_TIMEOUT", _DEFAULT_TCP_IDLE_TIMEOUT, minimum=0.1
        )
        udp_session_timeout = _parse_float_env(
            "SANA_GPS_UDP_SESSION_TIMEOUT", _DEFAULT_UDP_SESSION_TIMEOUT, minimum=0.1
        )
        max_tcp_connections = _parse_int_env(
            "SANA_GPS_MAX_TCP_CONNECTIONS", _DEFAULT_MAX_TCP_CONNECTIONS, minimum=1
        )
        max_udp_sessions = _parse_int_env(
            "SANA_GPS_MAX_UDP_SESSIONS", _DEFAULT_MAX_UDP_SESSIONS, minimum=1
        )
        max_datagram_size = _parse_int_env(
            "SANA_GPS_MAX_DATAGRAM_SIZE", _DEFAULT_MAX_DATAGRAM_SIZE, minimum=1
        )

        capture_file = os.getenv("SANA_GPS_CAPTURE_FILE", "").strip() or None

        log_level = os.getenv(
            "SANA_GPS_LOG_LEVEL", _DEFAULT_LOG_LEVEL
        ).strip().upper()
        if log_level not in _ALLOWED_LOG_LEVELS:
            allowed = ", ".join(sorted(_ALLOWED_LOG_LEVELS))
            raise ConfigurationError(
                f"SANA_GPS_LOG_LEVEL must be one of: {allowed}"
            )

        return cls(
            host=host,
            tcp_port=tcp_port,
            udp_port=udp_port,
            log_level=log_level,
            tcp_idle_timeout=tcp_idle_timeout,
            udp_session_timeout=udp_session_timeout,
            max_tcp_connections=max_tcp_connections,
            max_udp_sessions=max_udp_sessions,
            max_datagram_size=max_datagram_size,
            capture_file=capture_file,
            database=DatabaseConfig.from_env(),
        )


def _parse_float_env(
    name: str,
    default: float,
    *,
    minimum: float | None = None,
) -> float:
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


def _parse_int_env(
    name: str,
    default: int,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
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
