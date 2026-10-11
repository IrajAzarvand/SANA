from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict

from app.config import DatabaseConfig
from app.database.pool import DatabaseConnectionPool
from app.processing.telemetry import NormalizedTelemetry
from app.repositories.gps_telemetry import GPSTelemetryRepository


DSN = os.getenv("SANA_GPS_TEST_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="requires the PostGIS integration database")


def _record(
    *,
    device_time: datetime,
    received_at: datetime,
    latitude: Decimal | None,
    longitude: Decimal | None,
    gps_valid: bool,
) -> NormalizedTelemetry:
    return NormalizedTelemetry(
        device_id=1,
        device_time=device_time,
        server_received_at=received_at,
        latitude=latitude,
        longitude=longitude,
        gps_valid=gps_valid,
        speed=Decimal("50.00"),
        heading=Decimal("90.00"),
        attributes={"integration": True},
    )


def test_postgres_persistence_dedup_ordering_and_last_valid_position() -> None:
    assert DSN
    params = conninfo_to_dict(DSN)
    config = DatabaseConfig(
        host=params.get("host", "127.0.0.1"),
        port=int(params.get("port", "5432")),
        name=params["dbname"],
        user=params["user"],
        password=params["password"],
        pool_min_size=1,
        pool_max_size=2,
    )
    pool = DatabaseConnectionPool(config)
    pool.open()
    try:
        repository = GPSTelemetryRepository(pool)
        t1 = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
        r1 = datetime(2026, 10, 10, 12, 0, 1, tzinfo=timezone.utc)
        valid = _record(
            device_time=t1,
            received_at=r1,
            latitude=Decimal("35.7123456"),
            longitude=Decimal("51.4234567"),
            gps_valid=True,
        )
        assert repository.save_batch((valid,), protocol="teltonika", raw_payload=b"valid-1") == 1

        # Older telemetry is retained in history but must not roll back CurrentState.
        older = _record(
            device_time=datetime(2026, 10, 10, 11, 0, tzinfo=timezone.utc),
            received_at=datetime(2026, 10, 10, 12, 1, tzinfo=timezone.utc),
            latitude=Decimal("34.0000000"),
            longitude=Decimal("50.0000000"),
            gps_valid=True,
        )
        repository.save_batch((older,), protocol="teltonika", raw_payload=b"older-1")

        # A newer No-Fix clears current coordinates but retains the last valid fix.
        no_fix = _record(
            device_time=datetime(2026, 10, 10, 13, 0, tzinfo=timezone.utc),
            received_at=datetime(2026, 10, 10, 13, 0, 1, tzinfo=timezone.utc),
            latitude=None,
            longitude=None,
            gps_valid=False,
        )
        repository.save_batch((no_fix,), protocol="teltonika", raw_payload=b"nofix-1")

        # Replay of an already committed packet is ACK-eligible, with no duplicate history.
        replay = _record(
            device_time=no_fix.device_time,
            received_at=datetime(2026, 10, 10, 13, 2, tzinfo=timezone.utc),
            latitude=None,
            longitude=None,
            gps_valid=False,
        )
        assert repository.save_batch((replay,), protocol="teltonika", raw_payload=b"nofix-1") == 1

        with psycopg.connect(DSN) as connection:
            current = connection.execute(
                """
                SELECT device_time, latitude, longitude, gps_valid,
                       last_valid_latitude, last_valid_longitude,
                       last_valid_device_time, last_seen
                FROM gps.current_state WHERE device_id = 1
                """
            ).fetchone()
            history_count = connection.execute(
                "SELECT count(*) FROM gps.location_history WHERE device_id = 1"
            ).fetchone()[0]
            raw_count = connection.execute(
                "SELECT count(*) FROM gps.raw_packet WHERE device_id = 1"
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
        pool.close()
