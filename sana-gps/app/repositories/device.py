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
    """Read-only, narrowly scoped access to the canonical SANA device registry.

    Subscription and business eligibility are intentionally not queried here.
    The GPS runtime may read device identity/model/protocol configuration, but
    never writes the business-owned Device row.
    """

    _SQL = """
        SELECT d.id, d.imei, d.management_status,
               COALESCE(NULLIF(dm.protocol, ''), NULLIF(d.protocol, ''), '') AS protocol,
               d.device_model_id
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
            # Subscription activity is business data and is intentionally not
            # queried here. This legacy compatibility field is not authoritative.
            data_active=False,
            device_model_id=row[4],
        )

    def find_all_identifiers(self) -> tuple[str, ...]:
        """Return registered IMEIs for diagnostics without reading business data."""
        with self._pool.connection() as connection:
            rows = connection.execute(
                "SELECT imei FROM public.fleet_device WHERE imei IS NOT NULL"
            ).fetchall()
        return tuple(row[0] for row in rows if row[0])
