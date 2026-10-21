from __future__ import annotations

import asyncio
import logging

from app.database.pool import DatabaseConnectionPool
from app.repositories.device import DeviceRepository
from app.traccar.client import TraccarClient

logger = logging.getLogger(__name__)


def sync_devices_once(client: TraccarClient, device_repository: DeviceRepository) -> int:
    """Ensure every SANA-registered device exists in Traccar; ignore all other IDs."""
    sana_ids = {
        str(identifier).strip()
        for identifier in device_repository.find_all_identifiers()
        if str(identifier).strip()
    }
    traccar_ids = {
        str(device.get("uniqueId") or "").strip()
        for device in client.list_devices()
        if str(device.get("uniqueId") or "").strip()
    }
    created = 0
    for identifier in sorted(sana_ids - traccar_ids):
        try:
            client.create_device(identifier)
            created += 1
            logger.info("Created Traccar device for SANA-registered identifier")
        except Exception:
            logger.exception("Could not synchronize a SANA-registered device to Traccar")
    return created


async def run_device_sync_worker(
    shutdown_event: asyncio.Event,
    client: TraccarClient,
    device_repository: DeviceRepository,
    interval_seconds: float = 60.0,
) -> None:
    """Periodically sync registered SANA devices; never stage Traccar-only devices."""
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
