from __future__ import annotations

from hashlib import sha256
from typing import Sequence

from app.database.pool import DatabaseConnectionPool
from psycopg.types.json import Jsonb
from app.processing.telemetry import NormalizedTelemetry


class GPSTelemetryRepository:
    """Persist normalized telemetry atomically, with packet-record deduplication."""

    _INSERT_SQL = """
        INSERT INTO fleet_gpstelemetry
            (device_id, protocol, gps_time, latitude, longitude, gps_valid,
             speed_kmh, heading_deg, altitude_m, satellites, attributes,
             fingerprint, raw_payload, received_at)
        VALUES
            (%s, %s, %s, %s, %s, %s,
             %s, %s, %s, %s, %s,
             %s, %s, COALESCE(%s, CURRENT_TIMESTAMP))
        ON CONFLICT (device_id, fingerprint) DO NOTHING
    """

    def __init__(self, pool: DatabaseConnectionPool) -> None:
        self._pool = pool

    def save(
        self, *, device_id: int, protocol: str, gps_time,
        latitude: float | None, longitude: float | None,
        speed_kmh: float | None, raw_payload: bytes,
    ) -> None:
        """Compatibility path for text protocols such as HQ."""
        fingerprint = sha256(protocol.encode("utf-8") + b"\x00" + raw_payload).hexdigest()
        gps_valid = latitude is not None and longitude is not None
        with self._pool.connection() as connection:
            connection.execute(
                self._INSERT_SQL,
                (
                    device_id, protocol, gps_time, latitude, longitude, gps_valid,
                    speed_kmh, None, None, None, Jsonb({}),
                    fingerprint, raw_payload, None,
                ),
            )

    def save_batch(
        self,
        records: Sequence[NormalizedTelemetry],
        *,
        protocol: str,
        raw_payload: bytes,
    ) -> int:
        """Commit a whole AVL packet atomically and return its accepted record count.

        Replayed records use the same stable per-record fingerprint and are ignored
        by PostgreSQL. A duplicate packet is still ACK-eligible after this method
        returns, because the earlier copy was already committed.
        """
        if not records:
            return 0

        with self._pool.connection() as connection:
            with connection.transaction():
                for index, record in enumerate(records):
                    fingerprint = sha256(
                        raw_payload + index.to_bytes(4, "big")
                    ).hexdigest()
                    connection.execute(
                        self._INSERT_SQL,
                        (
                            record.device_id,
                            protocol,
                            record.device_time,
                            record.latitude,
                            record.longitude,
                            record.gps_valid,
                            record.speed_kmh,
                            record.heading_deg,
                            record.altitude_m,
                            record.satellites,
                            Jsonb(record.attributes),
                            fingerprint,
                            raw_payload,
                            record.server_received_at,
                        ),
                    )

        return len(records)
