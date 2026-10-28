"""Complete or correct SANA device brand/model from the protocol Traccar receives.

Traccar does not detect a physical brand or model; it only records the protocol a
device used (for example ``teltonika`` or ``gt06``) on its latest position. SANA
therefore resolves the catalog model by protocol and only writes a value when the
verified catalog contains exactly one distinct model for that protocol.
"""

from __future__ import annotations

from django.utils import timezone

from .models import Device, DeviceModel
from .traccar_api import traccar_current_positions, traccar_devices

UNRESOLVED_PROTOCOLS = frozenset({"", "unknown", "clones"})


def normalize_protocol(value: object) -> str:
    return str(value or "").strip().lower()


def build_protocols_by_unique_id(
    traccar_devices: list[dict],
    traccar_positions: list[dict],
) -> dict[str, str]:
    """Map each Traccar uniqueId to the protocol reported for its latest position."""
    unique_id_by_device_id: dict[int, str] = {}
    protocols_by_unique_id: dict[str, str] = {}

    for item in traccar_devices:
        unique_id = str(item.get("uniqueId") or "").strip()
        if not unique_id:
            continue
        protocol = normalize_protocol(item.get("protocol"))
        if protocol not in UNRESOLVED_PROTOCOLS:
            protocols_by_unique_id[unique_id] = protocol
        try:
            unique_id_by_device_id[int(item["id"])] = unique_id
        except (KeyError, TypeError, ValueError):
            continue

    for position in traccar_positions:
        protocol = normalize_protocol(position.get("protocol"))
        if protocol in UNRESOLVED_PROTOCOLS:
            continue
        try:
            device_id = int(position.get("deviceId"))
        except (TypeError, ValueError):
            continue
        unique_id = unique_id_by_device_id.get(device_id)
        if unique_id:
            protocols_by_unique_id[unique_id] = protocol

    return protocols_by_unique_id


def select_unique_catalog_model(protocol: str, catalog: list[DeviceModel]) -> DeviceModel | None:
    """Return the only distinct catalog model for a protocol, or None.

    Ambiguous protocols (such as ``gt06``, shared by many manufacturers) stay
    unresolved instead of guessing a model.
    """
    normalized = normalize_protocol(protocol)
    if normalized in UNRESOLVED_PROTOCOLS:
        return None

    by_name: dict[tuple[str, str], DeviceModel] = {}
    for model in catalog:
        if normalize_protocol(model.protocol) != normalized:
            continue
        key = (model.manufacturer.casefold(), model.name.casefold())
        by_name.setdefault(key, model)

    if len(by_name) != 1:
        return None
    return next(iter(by_name.values()))


def _matches_protocol(existing: DeviceModel, protocol: str) -> bool:
    return normalize_protocol(existing.protocol) == normalize_protocol(protocol)


def sync_device_models_from_traccar(
    *,
    dry_run: bool = False,
    traccar_devices_payload: list[dict] | None = None,
    traccar_positions_payload: list[dict] | None = None,
    catalog: list[DeviceModel] | None = None,
    devices=None,
) -> dict:
    """Fill blank brand/model and correct values that contradict the received protocol.

    A blank device_model is filled when the protocol maps to exactly one distinct
    verified catalog model. A registered model is replaced only when its protocol
    contradicts the detected one; compatible models and ambiguous protocols are
    left untouched.
    """
    traccar_devices_payload = (
        traccar_devices() if traccar_devices_payload is None else traccar_devices_payload
    )
    traccar_positions_payload = (
        traccar_current_positions()
        if traccar_positions_payload is None
        else traccar_positions_payload
    )
    protocols_by_unique_id = build_protocols_by_unique_id(
        traccar_devices_payload, traccar_positions_payload
    )

    if catalog is None:
        catalog = list(DeviceModel.objects.filter(is_verified=True))
    if devices is None:
        devices = Device.objects.select_related("device_model").filter(
            imei__in=list(protocols_by_unique_id)
        )

    stats = {
        "scanned": 0,
        "assigned": 0,
        "corrected": 0,
        "unchanged": 0,
        "unresolved": 0,
        "changes": [],
    }

    for device in devices:
        protocol = protocols_by_unique_id.get(str(device.imei).strip())
        if protocol is None:
            continue
        stats["scanned"] += 1

        candidate = select_unique_catalog_model(protocol, catalog)
        if candidate is None:
            stats["unresolved"] += 1
            continue

        existing = device.device_model
        if existing is not None and _matches_protocol(existing, protocol):
            stats["unchanged"] += 1
            continue

        stats["corrected" if existing is not None else "assigned"] += 1
        stats["changes"].append(
            {
                "imei": device.imei,
                "protocol": protocol,
                "previous": str(existing) if existing is not None else "",
                "model": str(candidate),
            }
        )
        if not dry_run:
            device.device_model = candidate
            device.updated_at = timezone.now()
            device.save(update_fields=["device_model", "updated_at"])

    return stats
