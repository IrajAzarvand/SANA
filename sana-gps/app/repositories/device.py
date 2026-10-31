from __future__ import annotations

from app.database.pool import DatabaseConnectionPool


class DeviceRepository:
    """Read SANA device identifiers and mirror protocol metadata reported by Traccar."""

    def __init__(self, pool: DatabaseConnectionPool) -> None:
        self._pool = pool

    def find_all_identifiers(self) -> tuple[str, ...]:
        """Return registered IMEIs; Traccar-only devices are never imported into SANA."""
        with self._pool.connection() as connection:
            rows = connection.execute(
                "SELECT imei FROM public.fleet_device WHERE imei IS NOT NULL"
            ).fetchall()
        return tuple(row[0] for row in rows if row[0])

    def set_traccar_protocol(self, imei: str, protocol: str) -> bool:
        """Mirror the protocol reported by a Traccar Position for a registered IMEI."""
        normalized_imei = str(imei or "").strip()
        normalized_protocol = str(protocol or "").strip().lower()
        if not normalized_imei or not normalized_protocol or len(normalized_protocol) > 50:
            return False
        with self._pool.connection() as connection:
            row = connection.execute(
                """
                UPDATE public.fleet_device
                SET protocol = %s
                WHERE imei = %s
                  AND protocol IS DISTINCT FROM %s
                RETURNING id
                """,
                (normalized_protocol, normalized_imei, normalized_protocol),
            ).fetchone()
        return row is not None
