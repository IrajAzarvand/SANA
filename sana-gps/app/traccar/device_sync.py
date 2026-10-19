from __future__ import annotations

import asyncio
import logging

from app.repositories.device import DeviceRepository
from app.traccar.client import TraccarClient
from app.traccar.pending_repository import TraccarPendingDeviceRepository

logger = logging.getLogger(__name__)


def sync_devices_once(
    client: TraccarClient,
    device_repository: DeviceRepository,
    pending_repository: TraccarPendingDeviceRepository,
) -> int:
    """Create missing SANA devices in Traccar and stage Traccar-only identifiers."""
    sana_ids = {
        identifier.strip()
        for identifier in device_repository.find_all_identifiers()
        if identifier and identifier.strip()
    }
    traccar_devices = client.list_devices()
    traccar_ids = {
        str(device.get("uniqueId") or "").strip()
        for device in traccar_devices
        if str(device.get("uniqueId") or "").strip()
    }
    created = 0
    for identifier in sorted(sana_ids - traccar_ids):
        try:
            client.create_device(identifier)
            created += 1
            logger.info("Created SANA device in Traccar: %s", identifier)
        except Exception:
            # Keep reconciling other devices; the next run retries this one.
            logger.exception("Could not synchronize SANA device IMEI=%s to Traccar", identifier)

    # Refresh after creating records, then identify Traccar devices not present
    # in SANA's authoritative fleet table. They never enter telemetry storage.
    refreshed = client.list_devices()
    for device in refreshed:
        unique_id = str(device.get("uniqueId") or "").strip()
        if not unique_id:
            continue
        if unique_id in sana_ids:
            pending_repository.mark_registered(unique_id)
        else:
            pending_repository.record_unknown(device)
    return created


async def run_device_sync_worker(
    shutdown_event: asyncio.Event,
    client: TraccarClient,
    device_repository: DeviceRepository,
    pending_repository: TraccarPendingDeviceRepository,
    *,
    interval_seconds: float,
) -> None:
    """Run reconciliation immediately, then periodically with retry on failures."""
    while not shutdown_event.is_set():
        try:
            created = await asyncio.to_thread(
                sync_devices_once, client, device_repository, pending_repository
            )
            if created:
                logger.info("Traccar reconciliation created %d device(s)", created)
        except Exception:
            logger.exception("Traccar reconciliation failed; retrying after interval")
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass
