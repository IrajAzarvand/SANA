from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict

from app.config import DatabaseConfig
from app.database.pool import DatabaseConnectionPool
from app.processing.telemetry import NormalizedTelemetry
from app.repositories.gps_telemetry import GPSTelemetryRepository


# The runtime DSN is used by the repository under test. The admin DSN is used
# only to provision and remove the isolated test device and its dependent rows.
DSN = os.getenv("SANA_GPS_TEST_DSN")
ADMIN_DSN = os.getenv("SANA_GPS_TEST_ADMIN_DSN")
pytestmark = pytest.mark.skipif(
    not DSN or not ADMIN_DSN,
    reason="requires SANA_GPS_TEST_DSN and SANA_GPS_TEST_ADMIN_DSN for isolated PostGIS integration testing",
)


def _record(
    *,
    device_id: int,
    device_time: datetime,
    received_at: datetime,
    latitude: Decimal | None,
    longitude: Decimal | None,
    gps_valid: bool,
) -> NormalizedTelemetry:
    return NormalizedTelemetry(
        device_id=device_id,
        device_time=device_time,
        server_received_at=received_at,
        latitude=latitude,
        longitude=longitude,
        gps_valid=gps_valid,
        speed=Decimal("50.00"),
        heading=Decimal("90.00"),
        attributes={"integration": True, "test_run": True},
    )


def _create_test_device(admin_dsn: str) -> tuple[int, str]:
    """Create a uniquely named, otherwise unassociated fleet device.

    Let PostgreSQL allocate the primary key through its identity/sequence. Using
    MAX(id) + 1 directly is racy and can collide with concurrent inserts.
    """
    imei = f"T{uuid.uuid4().hex[:19]}"
    with psycopg.connect(admin_dsn) as connection:
        row = connection.execute(
            """
            INSERT INTO public.fleet_device (imei)
            VALUES (%s)
            RETURNING id
            """,
            (imei,),
        ).fetchone()
        if row is None:
            raise RuntimeError("PostgreSQL did not return the test device ID")
        return int(row[0]), imei


def _cleanup_test_device(admin_dsn: str, device_id: int, imei: str) -> None:
    """Remove only rows attached to the device created by this test run."""
    with psycopg.connect(admin_dsn) as connection:
        with connection.transaction():
            # Remove dependent rows first, respecting foreign-key relationships.
            connection.execute("DELETE FROM gps.trip WHERE device_id = %s", (device_id,))
            connection.execute(
                "DELETE FROM gps.event WHERE device_id = %s", (device_id,)
            )
            connection.execute(
                "DELETE FROM gps.vehicle_geofence_state WHERE device_id = %s",
                (device_id,),
            )
            connection.execute(
                "DELETE FROM gps.current_state WHERE device_id = %s", (device_id,)
            )
            connection.execute(
                "DELETE FROM gps.location_history WHERE device_id = %s", (device_id,)
            )
            connection.execute(
                "DELETE FROM gps.raw_packet WHERE device_id = %s", (device_id,)
            )
            # Legacy Django telemetry table, if any rows were written by a hook.
            connection.execute(
                "DELETE FROM public.fleet_gpstelemetry WHERE device_id = %s",
                (device_id,),
            )

            deleted = connection.execute(
                "DELETE FROM public.fleet_device WHERE id = %s AND imei = %s",
                (device_id, imei),
            ).rowcount
            if deleted != 1:
                raise RuntimeError(
                    "Cleanup safety check failed: the uniquely created test device "
                    f"(id={device_id}) was not deleted exactly once (deleted={deleted})"
                )

            # Verify that all known GPS data tables are clear for this test device.
            checks = (
                ("gps.raw_packet", "SELECT count(*) FROM gps.raw_packet WHERE device_id = %s"),
                ("gps.location_history", "SELECT count(*) FROM gps.location_history WHERE device_id = %s"),
                ("gps.current_state", "SELECT count(*) FROM gps.current_state WHERE device_id = %s"),
                ("gps.event", "SELECT count(*) FROM gps.event WHERE device_id = %s"),
                ("gps.trip", "SELECT count(*) FROM gps.trip WHERE device_id = %s"),
                ("gps.vehicle_geofence_state", "SELECT count(*) FROM gps.vehicle_geofence_state WHERE device_id = %s"),
                ("public.fleet_gpstelemetry", "SELECT count(*) FROM public.fleet_gpstelemetry WHERE device_id = %s"),
                ("public.fleet_device", "SELECT count(*) FROM public.fleet_device WHERE id = %s AND imei = %s"),
            )
            for table_name, query in checks:
                params = (device_id, imei) if table_name == "public.fleet_device" else (device_id,)
                remaining = connection.execute(query, params).fetchone()[0]
                if remaining:
                    raise RuntimeError(
                        f"Cleanup verification failed: {remaining} row(s) remain in "
                        f"{table_name} for test device id={device_id}"
                    )


def test_postgres_persistence_dedup_ordering_and_last_valid_position() -> None:
    assert DSN and ADMIN_DSN
    params = conninfo_to_dict(DSN)
    config = DatabaseConfig(
        host=params.get("host", "127.0.0.1"),
        port=int(params.get("port", "5432")),
        name=params["dbname"],
        user=params["user"],
        password=params.get("password", ""),
        pool_min_size=1,
        pool_max_size=2,
    )

    # Setup uses an admin connection; runtime persistence uses the configured
    # service connection, exercising the same SQL permissions as the GPS service.
    device_id, test_imei = _create_test_device(ADMIN_DSN)
    pool = DatabaseConnectionPool(config)
    try:
        pool.open()
        repository = GPSTelemetryRepository(pool)
        t1 = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
        r1 = datetime(2026, 10, 10, 12, 0, 1, tzinfo=timezone.utc)
        valid = _record(
            device_id=device_id,
            device_time=t1,
            received_at=r1,
            latitude=Decimal("35.7123456"),
            longitude=Decimal("51.4234567"),
            gps_valid=True,
        )
        assert repository.save_batch(
            (valid,), protocol="teltonika", raw_payload=f"{test_imei}:valid-1".encode()
        ) == 1

        # Older telemetry is retained in history but must not roll back CurrentState.
        older = _record(
            device_id=device_id,
            device_time=datetime(2026, 10, 10, 11, 0, tzinfo=timezone.utc),
            received_at=datetime(2026, 10, 10, 12, 1, tzinfo=timezone.utc),
            latitude=Decimal("34.0000000"),
            longitude=Decimal("50.0000000"),
            gps_valid=True,
        )
        assert repository.save_batch(
            (older,), protocol="teltonika", raw_payload=f"{test_imei}:older-1".encode()
        ) == 1

        # A newer No-Fix clears current coordinates but retains the last valid fix.
        no_fix = _record(
            device_id=device_id,
            device_time=datetime(2026, 10, 10, 13, 0, tzinfo=timezone.utc),
            received_at=datetime(2026, 10, 10, 13, 0, 1, tzinfo=timezone.utc),
            latitude=None,
            longitude=None,
            gps_valid=False,
        )
        assert repository.save_batch(
            (no_fix,), protocol="teltonika", raw_payload=f"{test_imei}:nofix-1".encode()
        ) == 1

        # Replay the exact same packet: no duplicate history, but last_seen advances.
        replay = _record(
            device_id=device_id,
            device_time=no_fix.device_time,
            received_at=datetime(2026, 10, 10, 13, 2, tzinfo=timezone.utc),
            latitude=None,
            longitude=None,
            gps_valid=False,
        )
        assert repository.save_batch(
            (replay,), protocol="teltonika", raw_payload=f"{test_imei}:nofix-1".encode()
        ) == 1

        with psycopg.connect(DSN) as connection:
            current = connection.execute(
                """
                SELECT device_time, latitude, longitude, gps_valid,
                       last_valid_latitude, last_valid_longitude,
                       last_valid_device_time, last_seen
                FROM gps.current_state WHERE device_id = %s
                """,
                (device_id,),
            ).fetchone()
            history_count = connection.execute(
                "SELECT count(*) FROM gps.location_history WHERE device_id = %s",
                (device_id,),
            ).fetchone()[0]
            raw_count = connection.execute(
                "SELECT count(*) FROM gps.raw_packet WHERE device_id = %s",
                (device_id,),
            ).fetchone()[0]

        assert current is not None
        assert current[0] == no_fix.device_time
        assert current[1] is None and current[2] is None and current[3] is False
        assert current[4] == Decimal("35.7123456")
        assert current[5] == Decimal("51.4234567")
        assert current[6] == t1
        assert current[7] == replay.server_received_at
        assert history_count == 3
        assert raw_count == 3
    finally:
        try:
            pool.close()
        finally:
            # Cleanup is attempted even when an assertion or repository call fails.
            _cleanup_test_device(ADMIN_DSN, device_id, test_imei)
