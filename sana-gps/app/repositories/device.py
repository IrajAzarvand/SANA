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
    # Canonical fleet_device.protocol, distinct from the model-preferred
    # effective protocol exposed through the protocol field.
    device_protocol: str = ""


class DeviceRepository:
    """Registered-device lookup plus a narrowly-scoped protocol auto-detection write.

    Registration by IMEI is the sole business eligibility gate for receiving
    telemetry. Management status and subscription assignment are intentionally
    not consulted here: warehouse, lost, faulty, disconnected, and other
    registered devices may still need to report their locations.

    The only business-field write allowed to the GPS runtime is the conditional
    protocol registration below. It never overwrites a non-empty device/model
    protocol and is safe against concurrent first connections.
    """

    _SQL = """
        SELECT d.id, d.imei, d.management_status,
               COALESCE(NULLIF(BTRIM(dm.protocol), ''), NULLIF(BTRIM(d.protocol), ''), '') AS protocol,
               d.device_model_id,
               TRUE AS data_active,
               COALESCE(d.protocol, '') AS device_protocol
        FROM public.fleet_device AS d
        LEFT JOIN public.fleet_devicemodel AS dm ON dm.id = d.device_model_id
        WHERE d.imei = %s
        LIMIT 1
    """

    _SET_DETECTED_PROTOCOL_SQL = """
        UPDATE public.fleet_device AS d
        SET protocol = CASE
            WHEN COALESCE(NULLIF(BTRIM(d.protocol), ''), '') = '' THEN %s
            ELSE d.protocol
        END
        WHERE d.id = %s
          AND (
              COALESCE(NULLIF(BTRIM(d.protocol), ''), '') = ''
              OR LOWER(BTRIM(d.protocol)) = %s
          )
          AND (
              d.device_model_id IS NULL
              OR EXISTS (
                  SELECT 1
                  FROM public.fleet_devicemodel AS dm
                  WHERE dm.id = d.device_model_id
                    AND (
                        COALESCE(NULLIF(BTRIM(dm.protocol), ''), '') = ''
                        OR LOWER(BTRIM(dm.protocol)) = %s
                    )
              )
          )
        RETURNING d.id
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
            device_protocol=row[6] or "",
        )

    def set_detected_protocol(self, device_id: int, protocol: str) -> bool:
        """Set a blank device protocol, or confirm an existing compatible value.

        The conditional UPDATE is the concurrency boundary: if a different
        protocol was configured or registered by another session first, no row
        is returned and the handshake must not be accepted.
        """
        normalized_protocol = protocol.strip().lower()
        if not normalized_protocol:
            return False
        with self._pool.connection() as connection:
            row = connection.execute(
                self._SET_DETECTED_PROTOCOL_SQL,
                (
                    normalized_protocol,
                    device_id,
                    normalized_protocol,
                    normalized_protocol,
                ),
            ).fetchone()
        return row is not None

    def find_all_identifiers(self) -> tuple[str, ...]:
        """Return registered IMEIs for diagnostics without reading business data."""
        with self._pool.connection() as connection:
            rows = connection.execute(
                "SELECT imei FROM public.fleet_device WHERE imei IS NOT NULL"
            ).fetchall()
        return tuple(row[0] for row in rows if row[0])
