from __future__ import annotations

from unittest.mock import MagicMock, Mock

from app.repositories.device import DeviceRecord, DeviceRepository


def test_find_by_imei_returns_registered_device_without_business_queries() -> None:
    connection = Mock()
    connection.execute.return_value.fetchone.return_value = (
        42, "352094082143253", "warehouse", "teltonika", 3
    )
    pool = MagicMock()
    pool.connection.return_value.__enter__.return_value = connection

    device = DeviceRepository(pool).find_by_imei("352094082143253")

    assert device == DeviceRecord(
        id=42,
        imei="352094082143253",
        management_status="warehouse",
        protocol="teltonika",
        data_active=False,
        device_model_id=3,
    )
    connection.execute.assert_called_once()
    sql = connection.execute.call_args.args[0].lower()
    assert "organizations_subscription" not in sql
    assert "update " not in sql
    assert "public.fleet_device" in sql


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
