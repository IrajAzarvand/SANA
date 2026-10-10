from __future__ import annotations

from dataclasses import dataclass

from app.database.pool import DatabaseConnectionPool


@dataclass(frozen=True, slots=True)
class DeviceRecord:
    id: int
    imei: str
    management_status: str
    protocol: str
    data_active: bool


class DeviceRepository:
    """Reads the SANA business Device registry without Django ORM."""

    _SQL = """
        SELECT
            d.id,
            d.imei,
            d.management_status,
            d.protocol,
            EXISTS (
                SELECT 1
                FROM organizations_subscriptiondevice sd
                JOIN organizations_subscription s
                  ON s.id = sd.subscription_id
                WHERE sd.device_id = d.id
                  AND sd.unassigned_at IS NULL
                  AND sd.start_date <= CURRENT_DATE
                  AND sd.end_date >= CURRENT_DATE
                  AND s.status = 'active'
            ) AS data_active
        FROM fleet_device d
        WHERE d.imei = %s
        LIMIT 1
    """

    def __init__(self, pool: DatabaseConnectionPool) -> None:
        self._pool = pool

    def find_by_imei(self, imei: str) -> DeviceRecord | None:
        with self._pool.connection() as connection:
            row = connection.execute(self._SQL, (imei,)).fetchone()

        if row is None:
            return None

        return DeviceRecord(
            id=row[0],
            imei=row[1],
            management_status=row[2],
            protocol=row[3] or "",
            data_active=row[4],
        )

    def set_detected_protocol(self, device_id: int, protocol: str) -> bool:
        """Persist the detected protocol without overwriting an existing value."""
        with self._pool.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE fleet_device
                SET protocol = %s
                WHERE id = %s AND (protocol IS NULL OR protocol = '')
                """,
                (protocol, device_id),
            )
            return cursor.rowcount == 1
