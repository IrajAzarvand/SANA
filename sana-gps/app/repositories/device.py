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
    device_model_id: int | None = None


class DeviceRepository:
    """Read-only access to the canonical SANA device registry and eligibility.

    The GPS runtime never writes business-owned Device or subscription records.
    Eligibility mirrors Device.is_data_active and SubscriptionDevice.is_active
    in the backend: the device must not be in a blocked management state and
    must have a currently assigned, in-date subscription-device link.
    """

    _SQL = """
        SELECT d.id, d.imei, d.management_status,
               COALESCE(NULLIF(dm.protocol, ''), NULLIF(d.protocol, ''), '') AS protocol,
               d.device_model_id,
               (
                   d.management_status NOT IN (
                       'faulty', 'ready', 'lost', 'stolen',
                       'disconnected', 'retired', 'disposed'
                   )
                   AND EXISTS (
                       SELECT 1
                       FROM public.organizations_subscriptiondevice AS sd
                       WHERE sd.device_id = d.id
                         AND sd.unassigned_at IS NULL
                         AND sd.start_date <= CURRENT_DATE
                         AND sd.end_date >= CURRENT_DATE
                   )
               ) AS data_active
        FROM public.fleet_device AS d
        LEFT JOIN public.fleet_devicemodel AS dm ON dm.id = d.device_model_id
        WHERE d.imei = %s
        LIMIT 1
    """

    def __init__(self, pool: DatabaseConnectionPool) -> None:
        self._pool = pool

    def find_by_imei(self, imei: str) -> DeviceRecord | None:
        normalized_imei = imei.strip()
        if not normalized_imei:
            return None
        with self._pool.connection() as connection:
            row = connection.execute(self._SQL, (normalized_imei,)).fetchone()
        if row is None:
            return None
        return DeviceRecord(
            id=row[0],
            imei=row[1],
            management_status=row[2],
            protocol=row[3] or "",
            device_model_id=row[4],
            data_active=bool(row[5]),
        )

    def find_all_identifiers(self) -> tuple[str, ...]:
        """Return registered IMEIs for diagnostics without reading business data."""
        with self._pool.connection() as connection:
            rows = connection.execute(
                "SELECT imei FROM public.fleet_device WHERE imei IS NOT NULL"
            ).fetchall()
        return tuple(row[0] for row in rows if row[0])
