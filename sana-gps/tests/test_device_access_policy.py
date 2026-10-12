from __future__ import annotations

import pytest

from app.policies.device_access import device_access_denial_reason, device_can_send_telemetry
from app.repositories.device import DeviceRecord


def make_device(*, data_active: bool) -> DeviceRecord:
    return DeviceRecord(
        id=1,
        imei="352094082143253",
        management_status="active",
        protocol="",
        data_active=data_active,
    )


def test_policy_allows_device_with_active_business_eligibility() -> None:
    device = make_device(data_active=True)
    assert device_access_denial_reason(device) is None
    assert device_can_send_telemetry(device) is True


@pytest.mark.parametrize("management_status", [
    "faulty", "ready", "lost", "stolen", "disconnected", "retired", "disposed",
])
def test_policy_rejects_device_without_active_business_eligibility(
    management_status: str,
) -> None:
    device = DeviceRecord(
        id=1,
        imei="352094082143253",
        management_status=management_status,
        protocol="",
        data_active=False,
    )
    assert device_access_denial_reason(device) == "device_not_data_active"
    assert device_can_send_telemetry(device) is False


def test_policy_is_independent_of_protocol_name() -> None:
    for protocol in ("teltonika", "gt06", "hq", "concox", ""):
        device = DeviceRecord(
            id=1,
            imei="352094082143253",
            management_status="active",
            protocol=protocol,
            data_active=False,
        )
        assert not device_can_send_telemetry(device)
