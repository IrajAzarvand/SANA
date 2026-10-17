from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from typing import Sequence

from psycopg.types.json import Jsonb

from app.database.pool import DatabaseConnectionPool
from app.processing.telemetry import NormalizedTelemetry


class GPSTelemetryRepository:
    """Persist packet, history, and current snapshot in one PostgreSQL transaction.

    The repository deliberately contains SQL persistence only. It does not
    decode packets, infer events, or calculate trips.
    """

    _INSERT_RAW_PACKET = """
        INSERT INTO gps.raw_packet
            (device_id, protocol, fingerprint, received_at, payload, metadata)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (device_id, fingerprint) DO NOTHING
        RETURNING id
    """

    _INSERT_HISTORY = """
        INSERT INTO gps.location_history (
            device_id, device_time, server_received_at,
            latitude, longitude, geom, gps_valid, accuracy, speed, heading,
            altitude, motion, ignition, satellites, battery_voltage,
            external_voltage, gsm_signal, odometer, engine_hours, fuel_level,
            attributes
        ) VALUES (
            %s, %s, %s, %s, %s,
            CASE WHEN %s THEN ST_SetSRID(ST_MakePoint(%s::double precision, %s::double precision), 4326) ELSE NULL END,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """

    # Match a telemetry sample independently of packet bytes and server receive
    # time. Devices may resend the same fix in a different packet or wrap it in
    # a packet whose non-GPS fields changed. Sensor values and attributes remain
    # part of identity so meaningful telemetry changes are not discarded.
    _EXISTS_HISTORY = """
        SELECT 1
        FROM gps.location_history
        WHERE device_id = %s
          AND device_time = %s
          AND latitude IS NOT DISTINCT FROM %s
          AND longitude IS NOT DISTINCT FROM %s
          AND gps_valid = %s
          AND accuracy IS NOT DISTINCT FROM %s
          AND speed IS NOT DISTINCT FROM %s
          AND heading IS NOT DISTINCT FROM %s
          AND altitude IS NOT DISTINCT FROM %s
          AND motion IS NOT DISTINCT FROM %s
          AND ignition IS NOT DISTINCT FROM %s
          AND satellites IS NOT DISTINCT FROM %s
          AND battery_voltage IS NOT DISTINCT FROM %s
          AND external_voltage IS NOT DISTINCT FROM %s
          AND gsm_signal IS NOT DISTINCT FROM %s
          AND odometer IS NOT DISTINCT FROM %s
          AND engine_hours IS NOT DISTINCT FROM %s
          AND fuel_level IS NOT DISTINCT FROM %s
          AND attributes = %s
        LIMIT 1
    """

    _LOCK_DEVICE_TELEMETRY = "SELECT pg_advisory_xact_lock(%s, %s)"

    _UPSERT_CURRENT_STATE = """
        INSERT INTO gps.current_state (
            device_id, device_time, server_received_at, last_seen, updated_at,
            latitude, longitude, geom, gps_valid,
            last_valid_latitude, last_valid_longitude, last_valid_geom,
            last_valid_device_time, last_valid_server_received_at, last_valid_accuracy,
            accuracy, speed, heading, altitude, motion, ignition, satellites,
            battery_voltage, external_voltage, gsm_signal, odometer, engine_hours,
            fuel_level, attributes
        ) VALUES (
            %s, %s, %s, %s, CURRENT_TIMESTAMP,
            %s, %s,
            CASE WHEN %s THEN ST_SetSRID(ST_MakePoint(%s::double precision, %s::double precision), 4326) ELSE NULL END,
            %s,
            CASE WHEN %s THEN %s::numeric ELSE NULL END,
            CASE WHEN %s THEN %s::numeric ELSE NULL END,
            CASE WHEN %s THEN ST_SetSRID(ST_MakePoint(%s::double precision, %s::double precision), 4326) ELSE NULL END,
            CASE WHEN %s THEN %s::timestamptz ELSE NULL END,
            CASE WHEN %s THEN %s::timestamptz ELSE NULL END,
            CASE WHEN %s THEN %s::numeric ELSE NULL END,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (device_id) DO UPDATE SET
            device_time = EXCLUDED.device_time,
            server_received_at = EXCLUDED.server_received_at,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            geom = EXCLUDED.geom,
            gps_valid = EXCLUDED.gps_valid,
            last_valid_latitude = CASE WHEN EXCLUDED.gps_valid
                THEN EXCLUDED.latitude ELSE gps.current_state.last_valid_latitude END,
            last_valid_longitude = CASE WHEN EXCLUDED.gps_valid
                THEN EXCLUDED.longitude ELSE gps.current_state.last_valid_longitude END,
            last_valid_geom = CASE WHEN EXCLUDED.gps_valid
                THEN EXCLUDED.geom ELSE gps.current_state.last_valid_geom END,
            last_valid_device_time = CASE WHEN EXCLUDED.gps_valid
                THEN EXCLUDED.device_time ELSE gps.current_state.last_valid_device_time END,
            last_valid_server_received_at = CASE WHEN EXCLUDED.gps_valid
                THEN EXCLUDED.server_received_at ELSE gps.current_state.last_valid_server_received_at END,
            last_valid_accuracy = CASE WHEN EXCLUDED.gps_valid
                THEN EXCLUDED.accuracy ELSE gps.current_state.last_valid_accuracy END,
            accuracy = EXCLUDED.accuracy,
            speed = EXCLUDED.speed,
            heading = EXCLUDED.heading,
            altitude = EXCLUDED.altitude,
            motion = EXCLUDED.motion,
            ignition = EXCLUDED.ignition,
            satellites = EXCLUDED.satellites,
            battery_voltage = EXCLUDED.battery_voltage,
            external_voltage = EXCLUDED.external_voltage,
            gsm_signal = EXCLUDED.gsm_signal,
            odometer = EXCLUDED.odometer,
            engine_hours = EXCLUDED.engine_hours,
            fuel_level = EXCLUDED.fuel_level,
            attributes = EXCLUDED.attributes,
            matched_latitude = CASE WHEN EXCLUDED.gps_valid
                THEN NULL ELSE gps.current_state.matched_latitude END,
            matched_longitude = CASE WHEN EXCLUDED.gps_valid
                THEN NULL ELSE gps.current_state.matched_longitude END,
            matched_geom = CASE WHEN EXCLUDED.gps_valid
                THEN NULL ELSE gps.current_state.matched_geom END,
            match_provider = CASE WHEN EXCLUDED.gps_valid
                THEN NULL ELSE gps.current_state.match_provider END,
            matched_at = CASE WHEN EXCLUDED.gps_valid
                THEN NULL ELSE gps.current_state.matched_at END,
            updated_at = CURRENT_TIMESTAMP
        WHERE gps.current_state.device_time IS NULL
           OR EXCLUDED.device_time > gps.current_state.device_time
    """

    def __init__(self, pool: DatabaseConnectionPool) -> None:
        self._pool = pool

    def save(
        self,
        *,
        device_id: int,
        protocol: str,
        gps_time: datetime,
        latitude: float | Decimal | None,
        longitude: float | Decimal | None,
        speed_kmh: float | Decimal | None,
        raw_payload: bytes,
    ) -> None:
        """Compatibility adapter for legacy handlers; persists via canonical tables."""
        received_at = datetime.now(timezone.utc)
        lat = self._as_decimal(latitude)
        lon = self._as_decimal(longitude)
        valid = (
            lat is not None and lon is not None
            and Decimal("-90") <= lat <= Decimal("90")
            and Decimal("-180") <= lon <= Decimal("180")
        )
        record = NormalizedTelemetry(
            device_id=device_id,
            device_time=gps_time,
            server_received_at=received_at,
            latitude=lat if valid else None,
            longitude=lon if valid else None,
            gps_valid=valid,
            speed=self._as_decimal(speed_kmh),
            attributes={},
        )
        self.save_batch((record,), protocol=protocol, raw_payload=raw_payload)

    def save_batch(
        self,
        records: Sequence[NormalizedTelemetry],
        *,
        protocol: str,
        raw_payload: bytes,
    ) -> int:
        """Atomically deduplicate a packet and write history/current state.

        If the packet was already committed, its records are returned as
        ACK-eligible without creating duplicate history or snapshot side effects.
        """
        if not records:
            return 0

        device_ids = {record.device_id for record in records}
        if len(device_ids) != 1:
            raise ValueError("one raw packet batch must belong to exactly one device")
        device_id = next(iter(device_ids))
        received_at = max(record.server_received_at for record in records)
        fingerprint = sha256(protocol.encode("utf-8") + b"\x00" + raw_payload).hexdigest()

        with self._pool.connection() as connection:
            with connection.transaction():
                raw_row = connection.execute(
                    self._INSERT_RAW_PACKET,
                    (
                        device_id,
                        protocol,
                        fingerprint,
                        received_at,
                        raw_payload,
                        Jsonb({"record_count": len(records)}),
                    ),
                ).fetchone()
                if raw_row is None:
                    # Replayed data has no telemetry side effects, but it still
                    # proves communication activity and is eligible for ACK.
                    connection.execute(
                        """
                        UPDATE gps.current_state
                        SET last_seen = GREATEST(last_seen, %s),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE device_id = %s
                        """,
                        (received_at, device_id),
                    )
                    return len(records)

                # Serialize telemetry writes per device. Without this lock,
                # two different packets carrying the same normalized sample
                # could both pass the history existence check concurrently.
                connection.execute(
                    self._LOCK_DEVICE_TELEMETRY,
                    (731042, device_id),
                )

                for record in records:
                    self._insert_history(connection, record)
                    self._upsert_current_state(connection, record)

                # Communication activity is independent of telemetry ordering.
                connection.execute(
                    """
                    UPDATE gps.current_state
                    SET last_seen = GREATEST(last_seen, %s),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE device_id = %s
                    """,
                    (received_at, device_id),
                )

        return len(records)

    def _insert_history(self, connection, record: NormalizedTelemetry) -> bool:
        # server_received_at is intentionally excluded: a retransmission is
        # expected to arrive later, but that must not create another history
        # point when the normalized telemetry itself is unchanged.
        r = record
        identity = (
            r.device_id,
            r.device_time,
            r.latitude,
            r.longitude,
            r.gps_valid,
            r.accuracy,
            r.speed,
            r.heading,
            r.altitude,
            r.motion,
            r.ignition,
            r.satellites,
            r.battery_voltage,
            r.external_voltage,
            r.gsm_signal,
            r.odometer,
            r.engine_hours,
            r.fuel_level,
            Jsonb(r.attributes),
        )
        existing = connection.execute(self._EXISTS_HISTORY, identity).fetchone()
        if existing is not None:
            return False

        connection.execute(self._INSERT_HISTORY, self._values(record))
        return True

    def _upsert_current_state(self, connection, record: NormalizedTelemetry) -> None:
        r = record
        connection.execute(
            self._UPSERT_CURRENT_STATE,
            (
                r.device_id, r.device_time, r.server_received_at, r.server_received_at,
                r.latitude, r.longitude, r.gps_valid, r.longitude, r.latitude, r.gps_valid,
                r.gps_valid, r.latitude, r.gps_valid, r.longitude,
                r.gps_valid, r.longitude, r.latitude,
                r.gps_valid, r.device_time, r.gps_valid, r.server_received_at,
                r.gps_valid, r.accuracy,
                r.accuracy, r.speed, r.heading, r.altitude, r.motion, r.ignition,
                r.satellites, r.battery_voltage, r.external_voltage, r.gsm_signal,
                r.odometer, r.engine_hours, r.fuel_level, Jsonb(r.attributes),
            ),
        )

    @staticmethod
    def _values(record: NormalizedTelemetry) -> tuple:
        r = record
        return (
            r.device_id, r.device_time, r.server_received_at,
            r.latitude, r.longitude, r.gps_valid, r.longitude, r.latitude,
            r.gps_valid, r.accuracy, r.speed, r.heading, r.altitude, r.motion,
            r.ignition, r.satellites, r.battery_voltage, r.external_voltage,
            r.gsm_signal, r.odometer, r.engine_hours, r.fuel_level, Jsonb(r.attributes),
        )

    @staticmethod
    def _as_decimal(value: float | Decimal | None) -> Decimal | None:
        if value is None:
            return None
        try:
            number = Decimal(str(value))
        except Exception:
            return None
        return number if number.is_finite() else None
