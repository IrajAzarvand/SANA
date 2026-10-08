from __future__ import annotations

from unittest.mock import Mock

from app.repositories.device import DeviceRecord, DeviceRepository


def test_find_by_imei_returns_registered_device() -> None:
    connection = Mock()
    connection.execute.return_value.fetchone.return_value = (
        42,
        "352094082143253",
        "warehouse",
        "teltonika",
        False,
    )

    pool = Mock()
    pool.connection.return_value.__enter__.return_value = connection

    device = DeviceRepository(pool).find_by_imei("352094082143253")

    assert device == DeviceRecord(
        id=42,
        imei="352094082143253",
        management_status="warehouse",
        protocol="teltonika",
        data_active=False,
    )
    connection.execute.assert_called_once()


def test_find_by_imei_returns_none_for_unknown_device() -> None:
    connection = Mock()
    connection.execute.return_value.fetchone.return_value = None

    pool = Mock()
    pool.connection.return_value.__enter__.return_value = connection

    assert DeviceRepository(pool).find_by_imei("000000000000000") is None


def test_terminal_device_cannot_complete_handshake() -> None:
    device = DeviceRecord(
        id=1,
        imei="352094082143253",
        management_status="lost",
        protocol="teltonika",
        data_active=False,
    )

    assert device.handshake_allowed is False


def test_warehouse_device_can_complete_handshake_without_active_service() -> None:
    device = DeviceRecord(
        id=1,
        imei="352094082143253",
        management_status="warehouse",
        protocol="teltonika",
        data_active=False,
    )

    assert device.handshake_allowed is True
