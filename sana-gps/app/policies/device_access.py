"""Shared telemetry intake policy for all GPS protocol adapters.

A device's management status and subscription state are business concerns and
must not suppress telemetry. Protocol handlers first resolve the exact IMEI
against the registered device table; unknown identifiers are rejected there.
"""

from __future__ import annotations

from app.repositories.device import DeviceRecord


def device_access_denial_reason(device: DeviceRecord) -> str | None:
    """Registered devices are always allowed to send telemetry.

    The argument is a DeviceRecord returned by DeviceRepository, so existence
    in the registry has already been established. Keep this shared function
    for compatibility and for one consistent gate across all protocol handlers.
    """
    return None


def device_can_send_telemetry(device: DeviceRecord) -> bool:
    """Return whether a registered device may send telemetry."""
    return True
