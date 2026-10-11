from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from app.processing.telemetry import NormalizedTelemetry
from app.repositories.gps_telemetry import GPSTelemetryRepository


NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


def _record() -> NormalizedTelemetry:
    return NormalizedTelemetry(
        device_id=9,
        device_time=NOW,
        server_received_at=NOW,
        latitude=Decimal("35.7000000"),
        longitude=Decimal("51.4000000"),
        gps_valid=True,
        speed=Decimal("42.00"),
        heading=Decimal("90.00"),
        altitude=Decimal("120.00"),
        attributes={"test": True},
    )


def _pool(*, raw_insert_result=(1,)):
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = raw_insert_result
    pool = MagicMock()
    pool.connection.return_value.__enter__.return_value = connection
    connection.transaction.return_value.__enter__.return_value = None
    return pool, connection


def test_save_batch_writes_raw_history_and_current_state_in_one_transaction() -> None:
    pool, connection = _pool()
    repository = GPSTelemetryRepository(pool)

    assert repository.save_batch((_record(),), protocol="teltonika", raw_payload=b"packet") == 1

    connection.transaction.assert_called_once()
    statements = [call.args[0] for call in connection.execute.call_args_list]
    assert any("INSERT INTO gps.raw_packet" in sql for sql in statements)
    assert any("INSERT INTO gps.location_history" in sql for sql in statements)
    assert any("INSERT INTO gps.current_state" in sql for sql in statements)
    assert not any("fleet_gpstelemetry" in sql for sql in statements)


def test_duplicate_packet_has_no_history_or_snapshot_side_effects() -> None:
    pool, connection = _pool(raw_insert_result=None)
    repository = GPSTelemetryRepository(pool)

    assert repository.save_batch((_record(),), protocol="teltonika", raw_payload=b"packet") == 1

    statements = [call.args[0] for call in connection.execute.call_args_list]
    assert len(statements) == 2
    assert any("UPDATE gps.current_state" in sql for sql in statements)
    assert not any("INSERT INTO gps.location_history" in sql for sql in statements)
    assert not any("INSERT INTO gps.current_state" in sql for sql in statements)


def test_batch_rejects_records_from_multiple_devices_before_database_access() -> None:
    pool, _ = _pool()
    first = _record()
    second = NormalizedTelemetry(
        device_id=10,
        device_time=NOW,
        server_received_at=NOW,
    )

    try:
        GPSTelemetryRepository(pool).save_batch(
            (first, second), protocol="teltonika", raw_payload=b"packet"
        )
    except ValueError as exc:
        assert "exactly one device" in str(exc)
    else:
        raise AssertionError("expected mixed-device batch to be rejected")
    pool.connection.assert_not_called()
