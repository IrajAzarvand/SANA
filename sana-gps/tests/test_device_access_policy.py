from __future__ import annotations

import pytest

from app.policies.device_access import device_access_denial_reason, device_can_send_telemetry
from app.repositories.device import DeviceRecord


def make_device(*, data_active: bool, management_status: str = "active") -> DeviceRecord:
    return DeviceRecord(
        id=1,
        imei="352094082143253",
        management_status=management_status,
        protocol="",
        data_active=data_active,
    )


def test_policy_allows_registered_device_with_active_business_eligibility() -> None:
    device = make_device(data_active=True)
    assert device_access_denial_reason(device) is None
    assert device_can_send_telemetry(device) is True


@pytest.mark.parametrize("management_status", [
    "warehouse", "sold", "installed", "active", "faulty", "ready", "lost",
    "stolen", "disconnected", "retired", "disposed",
])
def test_policy_allows_registered_device_regardless_of_management_status(
    management_status: str,
) -> None:
    device = make_device(data_active=False, management_status=management_status)
    assert device_access_denial_reason(device) is None
    assert device_can_send_telemetry(device) is True


def test_policy_is_independent_of_protocol_name() -> None:
    for protocol in ("teltonika", "gt06", "hq", "concox", ""):
        device = DeviceRecord(
            id=1,
            imei="352094082143253",
            management_status="warehouse",
            protocol=protocol,
            data_active=False,
        )
        assert device_can_send_telemetry(device)
