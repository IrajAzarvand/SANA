from __future__ import annotations

from datetime import datetime

from app.database.pool import DatabaseConnectionPool
from app.protocols.gt06 import GT06Position


class GT06PositionRepository:
    """Persists decoded GT06 position reports into fleet.GT06Position."""

    def __init__(self, pool: DatabaseConnectionPool) -> None:
        self._pool = pool

    def save(self, *, device_id: int, position: GT06Position, raw_frame: bytes) -> None:
        with self._pool.connection() as connection:
            connection.execute(
                """
                INSERT INTO fleet_gt06position
                    (device_id, gps_time, latitude, longitude, speed_kmh,
                     course, satellites, raw_frame, received_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """,
                (
                    device_id,
                    position.gps_time,
                    position.latitude,
                    position.longitude,
                    position.speed_kmh,
                    position.course,
                    position.satellites,
                    raw_frame,
                ),
            )
