from __future__ import annotations

from app.database.pool import DatabaseConnectionPool


class TraccarPendingDeviceRepository:
    """Keep Traccar-only device observations separate from SANA's official fleet."""

    _UPSERT_UNKNOWN = """
        INSERT INTO gps.traccar_unknown_device
            (traccar_device_id, unique_id, name, traccar_status, first_seen_at,
             last_seen_at, last_synced_at, review_status, metadata)
        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s, CURRENT_TIMESTAMP, 'pending', %s)
        ON CONFLICT (unique_id) DO UPDATE SET
            traccar_device_id = EXCLUDED.traccar_device_id,
            name = EXCLUDED.name,
            traccar_status = EXCLUDED.traccar_status,
            last_seen_at = GREATEST(
                gps.traccar_unknown_device.last_seen_at,
                EXCLUDED.last_seen_at
            ),
            last_synced_at = CURRENT_TIMESTAMP,
            metadata = EXCLUDED.metadata
    """

    def __init__(self, pool: DatabaseConnectionPool) -> None:
        self._pool = pool

    def check_schema(self) -> None:
        with self._pool.connection() as connection:
            row = connection.execute(
                "SELECT to_regclass('gps.traccar_unknown_device')"
            ).fetchone()
        if row is None or row[0] is None:
            raise RuntimeError(
                "Missing gps.traccar_unknown_device; apply "
                "sana-gps/sql/0009_traccar_integration.sql before starting SANA GPS"
            )

    def record_unknown(self, device: dict) -> bool:
        unique_id = str(device.get("uniqueId") or "").strip()
        if not unique_id:
            return False
        device_id = device.get("id")
        if device_id is None:
            return False
        try:
            traccar_device_id = int(device_id)
        except (TypeError, ValueError):
            return False
        last_seen = device.get("lastUpdate")
        metadata = {
            "category": device.get("category"),
            "disabled": device.get("disabled"),
            "positionId": device.get("positionId"),
        }
        with self._pool.connection() as connection:
            connection.execute(
                self._UPSERT_UNKNOWN,
                (
                    traccar_device_id,
                    unique_id[:128],
                    str(device.get("name") or unique_id)[:160],
                    str(device.get("status") or "unknown")[:32],
                    last_seen,
                    __import__("psycopg").types.json.Jsonb(metadata),
                ),
            )
        return True

    def mark_registered(self, unique_id: str) -> None:
        with self._pool.connection() as connection:
            connection.execute(
                """
                UPDATE gps.traccar_unknown_device
                SET review_status = 'registered',
                    last_synced_at = CURRENT_TIMESTAMP
                WHERE unique_id = %s
                """,
                (unique_id,),
            )
