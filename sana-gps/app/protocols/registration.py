from __future__ import annotations

from app.repositories.device import DeviceRecord, DeviceRepository


def confirm_detected_protocol(
    repository: DeviceRepository,
    device: DeviceRecord,
    detected_protocol: str,
) -> bool:
    """Validate and persist a protocol discovered during a successful handshake.

    This is the shared policy for every protocol handler, including handlers
    added in the future. A model-level protocol is authoritative when present;
    a non-empty device-level protocol is never overwritten. If the canonical
    device protocol is blank, the repository atomically records the detected
    value only when it is compatible with both the device and its model.
    """
    protocol = str(detected_protocol).strip().lower()
    if not protocol:
        return False

    effective_protocol = (device.protocol or "").strip().lower()
    if effective_protocol and effective_protocol != protocol:
        return False

    configured_device_protocol = (device.device_protocol or "").strip().lower()
    if configured_device_protocol:
        return configured_device_protocol == protocol

    # The repository performs an atomic conditional update. It returns False
    # if another connection registered a conflicting protocol concurrently.
    return repository.set_detected_protocol(device.id, protocol)
