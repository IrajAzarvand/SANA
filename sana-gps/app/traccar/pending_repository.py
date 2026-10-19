from __future__ import annotations

from datetime import datetime
from typing import Iterable

from psycopg.types.json import Jsonb

from app.database.pool import DatabaseConnectionPool


def _parse_timestamp(value) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        result = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if result.tzinfo is None:
        from datetime import timezone
        return result.replace(tzinfo=timezone.utc)
    return result


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
        self._available = False

    def check_schema(self) -> bool:
        """Check staging schema without taking down the existing GPS service."""
        try:
            with self._pool.connection() as connection:
                row = connection.execute(
                    "SELECT to_regclass('gps.traccar_unknown_device')"
                ).fetchone()
            self._available = bool(row and row[0])
        except Exception:
            self._available = False
        return self._available

    def record_unknown_many(self, devices: Iterable[dict]) -> int:
        if not self._available:
            return 0
        rows = []
        for device in devices:
            unique_id = str(device.get("uniqueId") or "").strip()
            if not unique_id or len(unique_id) > 128 or device.get("id") is None:
                continue
            try:
                traccar_device_id = int(device["id"])
            except (TypeError, ValueError):
                continue
            metadata = {
                "category": device.get("category"),
                "disabled": device.get("disabled"),
                "positionId": device.get("positionId"),
            }
            rows.append((
                traccar_device_id,
                unique_id,
                str(device.get("name") or unique_id)[:160],
                str(device.get("status") or "unknown")[:32],
                _parse_timestamp(device.get("lastUpdate")),
                Jsonb(metadata),
            ))
        if not rows:
            return 0
        with self._pool.connection() as connection:
            with connection.transaction():
                connection.executemany(self._UPSERT_UNKNOWN, rows)
        return len(rows)

    def mark_registered_many(self, unique_ids: Iterable[str]) -> int:
        if not self._available:
            return 0
        identifiers = tuple({item.strip() for item in unique_ids if item and item.strip()})
        if not identifiers:
            return 0
        with self._pool.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE gps.traccar_unknown_device
                SET review_status = 'registered',
                    last_synced_at = CURRENT_TIMESTAMP
                WHERE unique_id = ANY(%s)
                  AND review_status <> 'registered'
                """,
                (list(identifiers),),
            )
            return cursor.rowcount
