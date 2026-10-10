from __future__ import annotations

from datetime import datetime

from app.database.pool import DatabaseConnectionPool


class GPSTelemetryRepository:
    """Persist normalized positions from any supported wire protocol."""

    def __init__(self, pool: DatabaseConnectionPool) -> None:
        self._pool = pool

    def save(
        self, *, device_id: int, protocol: str, gps_time: datetime,
        latitude: float, longitude: float, speed_kmh: float, raw_payload: bytes,
    ) -> None:
        with self._pool.connection() as connection:
            connection.execute(
                """
                INSERT INTO fleet_gpstelemetry
                    (device_id, protocol, gps_time, latitude, longitude,
                     speed_kmh, raw_payload, received_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """,
                (device_id, protocol, gps_time, latitude, longitude,
                 speed_kmh, raw_payload),
            )
