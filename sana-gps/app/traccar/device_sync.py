from __future__ import annotations

import asyncio
import logging

from app.database.pool import DatabaseConnectionPool
from app.repositories.device import DeviceRepository
from app.traccar.client import TraccarClient

logger = logging.getLogger(__name__)


def sync_devices_once(client: TraccarClient, device_repository: DeviceRepository) -> int:
    """Ensure registered SANA devices exist in Traccar and mirror reported protocols."""
    sana_ids = {
        str(identifier).strip()
        for identifier in device_repository.find_all_identifiers()
        if str(identifier).strip()
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
            device = client.create_device(identifier)
            traccar_devices.append(device)
            created += 1
            logger.info("Created Traccar device for SANA-registered identifier")
        except Exception:
            logger.exception("Could not synchronize a SANA-registered device to Traccar")

    traccar_by_id = {
        int(device["id"]): str(device.get("uniqueId") or "").strip()
        for device in traccar_devices
        if device.get("id") is not None and str(device.get("uniqueId") or "").strip()
    }
    protocol_updates = 0
    try:
        positions = client.list_current_positions()
    except Exception:
        logger.exception("Could not read current Traccar positions for protocol synchronization")
        positions = []

    for position in positions:
        try:
            traccar_id = int(position["deviceId"])
        except (KeyError, TypeError, ValueError):
            continue
        imei = traccar_by_id.get(traccar_id)
        protocol = str(position.get("protocol") or "").strip()
        if not imei or imei not in sana_ids or not protocol:
            continue
        try:
            if device_repository.set_traccar_protocol(imei, protocol):
                protocol_updates += 1
        except Exception:
            logger.exception("Could not mirror Traccar protocol for a registered SANA device")
    if protocol_updates:
        logger.info("Mirrored Traccar protocol metadata for %d SANA device(s)", protocol_updates)
    return created


async def run_device_sync_worker(
    shutdown_event: asyncio.Event,
    client: TraccarClient,
    device_repository: DeviceRepository,
    interval_seconds: float = 60.0,
) -> None:
    """Periodically reconcile registered SANA devices and their Traccar protocol metadata."""
    while not shutdown_event.is_set():
        try:
            created = await asyncio.to_thread(sync_devices_once, client, device_repository)
            if created:
                logger.info("Traccar reconciliation created %d SANA device(s)", created)
        except Exception:
            logger.exception("Traccar device reconciliation failed; retrying")
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass
