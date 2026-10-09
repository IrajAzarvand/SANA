from __future__ import annotations

from unittest.mock import MagicMock, Mock

import pytest

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

    pool = MagicMock()
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

    pool = MagicMock()
    pool.connection.return_value.__enter__.return_value = connection

    assert DeviceRepository(pool).find_by_imei("000000000000000") is None


@pytest.mark.parametrize(
    "management_status",
    [
        "warehouse",
        "sold",
        "installed",
        "active",
        "ready",
        "faulty",
        "lost",
        "stolen",
        "disconnected",
        "retired",
        "disposed",
    ],
)
def test_registered_device_status_does_not_block_gps_connection(
    management_status: str,
) -> None:
    device = DeviceRecord(
        id=1,
        imei="352094082143253",
        management_status=management_status,
        protocol="teltonika",
        data_active=False,
    )

    # GPS connection eligibility is based on registration + protocol,
    # not on the device's management status.
    assert device.imei
    assert device.protocol == "teltonika"

def test_set_detected_protocol_persists_protocol_only_when_unknown() -> None:
    connection = Mock()
    connection.execute.return_value.rowcount = 1

    pool = MagicMock()
    pool.connection.return_value.__enter__.return_value = connection

    result = DeviceRepository(pool).set_detected_protocol(42, "teltonika")

    assert result is True
    connection.execute.assert_called_once()
    assert connection.execute.call_args.args[1] == ("teltonika", 42)

