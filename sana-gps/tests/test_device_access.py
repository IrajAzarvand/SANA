from __future__ import annotations

from app.policies.device_access import (
    device_access_denial_reason,
    device_can_send_telemetry,
)
from app.repositories.device import DeviceRecord


def test_registered_device_is_eligible_independent_of_management_status() -> None:
    statuses = ("warehouse", "active", "faulty", "ready", "lost", "stolen",
                "disconnected", "retired", "disposed", "sold")
    for status in statuses:
        device = DeviceRecord(
            id=1,
            imei="9176515720",
            management_status=status,
            protocol="hq*",
            data_active=False,
        )
        assert device_access_denial_reason(device) is None
        assert device_can_send_telemetry(device) is True
