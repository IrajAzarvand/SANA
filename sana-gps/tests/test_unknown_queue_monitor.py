import asyncio
from unittest.mock import patch

import pytest

from app.main import _monitor_unknown_protocol_queue


@pytest.mark.asyncio
async def test_queue_monitor_refreshes_registered_devices_without_restart():
    shutdown_event = asyncio.Event()
    scanned_identifiers = []

    class FakeDeviceRepository:
        def find_all_identifiers(self):
            return ("9176515720",)

    class FakeQueueRepository:
        def match_pending_sessions(self, identifiers):
            scanned_identifiers.append(identifiers)
            return 1

    with patch("app.main._UNKNOWN_QUEUE_POLL_SECONDS", 0.001):
        task = asyncio.create_task(
            _monitor_unknown_protocol_queue(
                shutdown_event, FakeDeviceRepository(), FakeQueueRepository()
            )
        )
        await asyncio.sleep(0.03)
        shutdown_event.set()
        await task

    assert scanned_identifiers
    assert all(item == ("9176515720",) for item in scanned_identifiers)
