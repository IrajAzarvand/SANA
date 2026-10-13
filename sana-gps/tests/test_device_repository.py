from __future__ import annotations

from unittest.mock import MagicMock, Mock

from app.repositories.device import DeviceRecord, DeviceRepository


def test_find_by_imei_returns_registered_device_without_business_eligibility_gate() -> None:
    connection = Mock()
    connection.execute.return_value.fetchone.return_value = (
        42, "352094082143253", "warehouse", "teltonika", 3, True, ""
    )
    pool = MagicMock()
    pool.connection.return_value.__enter__.return_value = connection

    device = DeviceRepository(pool).find_by_imei("352094082143253")

    assert device == DeviceRecord(
        id=42,
        imei="352094082143253",
        management_status="warehouse",
        protocol="teltonika",
        data_active=True,
        device_model_id=3,
        device_protocol="",
    )
    connection.execute.assert_called_once()
    sql = connection.execute.call_args.args[0].lower()
    assert "public.organizations_subscriptiondevice" not in sql
    assert "unassigned_at is null" not in sql
    assert "public.fleet_device" in sql
    assert "true as data_active" in sql
    assert "update " not in sql


def test_find_by_imei_returns_none_for_unknown_device() -> None:
    connection = Mock()
    connection.execute.return_value.fetchone.return_value = None
    pool = MagicMock()
    pool.connection.return_value.__enter__.return_value = connection

    assert DeviceRepository(pool).find_by_imei("000000000000000") is None


def test_find_by_imei_rejects_blank_identifier_without_query() -> None:
    pool = MagicMock()
    assert DeviceRepository(pool).find_by_imei("  ") is None
    pool.connection.assert_not_called()


def test_find_all_identifiers_reads_only_imei() -> None:
    connection = Mock()
    connection.execute.return_value.fetchall.return_value = [("123",), ("456",)]
    pool = MagicMock()
    pool.connection.return_value.__enter__.return_value = connection

    assert DeviceRepository(pool).find_all_identifiers() == ("123", "456")
    sql = connection.execute.call_args.args[0].lower()
    assert sql.strip().startswith("select imei from public.fleet_device")


def test_set_detected_protocol_calls_the_restricted_generic_registration_function() -> None:
    connection = Mock()
    connection.execute.return_value.fetchone.return_value = (True,)
    pool = MagicMock()
    pool.connection.return_value.__enter__.return_value = connection

    assert DeviceRepository(pool).set_detected_protocol(42, "  future-protocol  ") is True

    sql, params = connection.execute.call_args.args
    assert "select gps.register_detected_device_protocol(%s, %s)" in sql.lower()
    assert params == (42, "future-protocol")


def test_set_detected_protocol_returns_false_when_protocol_is_not_compatible() -> None:
    connection = Mock()
    connection.execute.return_value.fetchone.return_value = None
    pool = MagicMock()
    pool.connection.return_value.__enter__.return_value = connection

    assert DeviceRepository(pool).set_detected_protocol(42, "teltonika") is False


def test_set_detected_protocol_rejects_empty_value_without_query() -> None:
    pool = MagicMock()

    assert DeviceRepository(pool).set_detected_protocol(42, "  ") is False
    pool.connection.assert_not_called()
