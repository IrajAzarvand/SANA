from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from app.processing.telemetry import NormalizedTelemetry
from app.repositories.gps_telemetry import GPSTelemetryRepository


NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 10, 10, 12, 5, tzinfo=timezone.utc)


def _record(*, received_at=NOW) -> NormalizedTelemetry:
    return NormalizedTelemetry(
        device_id=9,
        device_time=NOW,
        server_received_at=received_at,
        latitude=Decimal("35.7000000"),
        longitude=Decimal("51.4000000"),
        gps_valid=True,
        speed=Decimal("42.00"),
        heading=Decimal("90.00"),
        altitude=Decimal("120.00"),
        attributes={"test": True},
    )


def _cursor(row=None):
    cursor = MagicMock()
    cursor.fetchone.return_value = row
    return cursor


def _pool(*, raw_insert_result=(1,), history_match_result=None):
    connection = MagicMock()

    def execute(sql, *args, **kwargs):
        if "INSERT INTO gps.raw_packet" in sql:
            return _cursor(raw_insert_result)
        if "SELECT 1" in sql and "FROM gps.location_history" in sql:
            return _cursor(history_match_result)
        return _cursor()

    connection.execute.side_effect = execute
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
    assert any("pg_advisory_xact_lock" in sql for sql in statements)
    assert any("SELECT 1" in sql and "gps.location_history" in sql for sql in statements)
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
    assert not any("pg_advisory_xact_lock" in sql for sql in statements)
    assert not any("SELECT 1" in sql and "gps.location_history" in sql for sql in statements)
    assert not any("INSERT INTO gps.location_history" in sql for sql in statements)
    assert not any("INSERT INTO gps.current_state" in sql for sql in statements)


def test_duplicate_normalized_sample_skips_history_insert() -> None:
    pool, connection = _pool(history_match_result=(42,))
    repository = GPSTelemetryRepository(pool)

    assert repository.save_batch((_record(),), protocol="hq", raw_payload=b"different-packet") == 1

    statements = [call.args[0] for call in connection.execute.call_args_list]
    assert any("SELECT 1" in sql and "gps.location_history" in sql for sql in statements)
    assert not any("INSERT INTO gps.location_history" in sql for sql in statements)
    # Snapshot upsert is still attempted; its device-time guard prevents an
    # identical/older sample from replacing a newer current state.
    assert any("INSERT INTO gps.current_state" in sql for sql in statements)


def test_history_identity_ignores_receive_time_but_includes_measurements() -> None:
    pool, connection = _pool()
    repository = GPSTelemetryRepository(pool)

    repository.save_batch(
        (_record(received_at=LATER),),
        protocol="hq",
        raw_payload=b"packet",
    )

    history_call = next(
        call for call in connection.execute.call_args_list
        if "SELECT 1" in call.args[0] and "gps.location_history" in call.args[0]
    )
    sql = history_call.args[0]
    params = history_call.args[1]
    assert "server_received_at" not in sql
    assert "speed IS NOT DISTINCT FROM %s" in sql
    assert "attributes = %s" in sql
    assert params[1] == NOW
    assert LATER not in params


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
