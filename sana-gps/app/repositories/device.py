from __future__ import annotations

from dataclasses import dataclass

from app.database.pool import DatabaseConnectionPool


_TERMINAL_MANAGEMENT_STATUSES = frozenset({
    "lost",
    "stolen",
    "retired",
    "disposed",
})


@dataclass(frozen=True, slots=True)
class DeviceRecord:
    id: int
    imei: str
    management_status: str
    protocol: str
    data_active: bool

    @property
    def handshake_allowed(self) -> bool:
        """Whether the registered device may complete protocol handshake."""
        return self.management_status not in _TERMINAL_MANAGEMENT_STATUSES


class DeviceRepository:
    """Reads the SANA business Device registry without Django ORM."""

    _SQL = """
        SELECT
            d.id,
            d.imei,
            d.management_status,
            dm.protocol,
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
        JOIN fleet_devicemodel dm
          ON dm.id = d.device_model_id
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
            protocol=row[3],
            data_active=row[4],
        )
