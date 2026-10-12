"""Shared business eligibility policy for all GPS protocol adapters.

Protocol handlers identify a device; this policy decides whether the runtime
may accept telemetry for it. Keep protocol-specific parsing out of this module.
"""

from __future__ import annotations

from app.repositories.device import DeviceRecord


def device_access_denial_reason(device: DeviceRecord) -> str | None:
    """Return a stable denial reason, or ``None`` when telemetry is allowed."""
    if not device.data_active:
        return "device_not_data_active"
    return None


def device_can_send_telemetry(device: DeviceRecord) -> bool:
    """Single protocol-independent gate for accepting a registered device."""
    return device_access_denial_reason(device) is None
