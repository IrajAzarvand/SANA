from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.protocols.decoders.teltonika import TeltonikaAVLDecoder
from app.protocols.dispatcher import ProtocolDispatcher
from app.protocols.registry import default_protocol_registry
from app.protocols.teltonika.handler import TeltonikaHandler
from app.protocols.types import ProtocolId
from app.repositories.device import DeviceRecord
from app.transport.session import SessionManager
from app.transport.tcp import TCPListener


IMEI = "352094082143253"
IMEI_FRAME = bytes.fromhex("000f333532303934303832313433323533")


class FakeDeviceRepository:
    def __init__(self, *, registered: bool = True) -> None:
        self.device = (
            DeviceRecord(
                id=7,
                imei=IMEI,
                management_status="active",
                protocol="",
                data_active=True,
            )
            if registered
            else None
        )
        self.detected_protocols: list[tuple[int, str]] = []

    def find_by_imei(self, imei: str) -> DeviceRecord | None:
        if self.device is not None and self.device.imei == imei:
            return self.device
        return None

    def set_detected_protocol(self, device_id: int, protocol: str) -> bool:
        self.detected_protocols.append((device_id, protocol))
        return self.device is not None and self.device.id == device_id


class FakeTelemetryRepository:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.saved: list[tuple[tuple, str, bytes]] = []

    def save_batch(self, records, *, protocol: str, raw_payload: bytes) -> int:
        if self.fail:
            raise RuntimeError("simulated PostgreSQL commit failure")
        batch = tuple(records)
        self.saved.append((batch, protocol, raw_payload))
        return len(batch)


def codec8_frame() -> bytes:
    timestamp = int(
        datetime(2026, 10, 10, 12, 4, 57, tzinfo=timezone.utc).timestamp() * 1000
    )
    record = (
        timestamp.to_bytes(8, "big")
        + b"\x00"
        + int(459321070).to_bytes(4, "big", signed=True)
        + int(378546450).to_bytes(4, "big", signed=True)
        + int(123).to_bytes(2, "big", signed=True)
        + int(180).to_bytes(2, "big")
        + b"\x08"
        + int(50).to_bytes(2, "big")
        + bytes((0, 1, 1, 239, 1, 0, 0, 0))
    )
    data = bytes((8, 1)) + record + b"\x01"
    crc = TeltonikaAVLDecoder._crc16_ibm(data)
    return (
        b"\x00\x00\x00\x00"
        + len(data).to_bytes(4, "big")
        + data
        + crc.to_bytes(4, "big")
    )


async def start_runtime(*, registered: bool = True, fail_persistence: bool = False):
    sessions = SessionManager()
    devices = FakeDeviceRepository(registered=registered)
    telemetry = FakeTelemetryRepository(fail=fail_persistence)
    handler = TeltonikaHandler(devices, telemetry, session_manager=sessions)
    dispatcher = ProtocolDispatcher(
        {ProtocolId.TELTONIKA: handler.handle},
        registry=default_protocol_registry(),
    )
    listener = TCPListener("127.0.0.1", 0, sessions, dispatcher.handle)
    await listener.start()
    assert listener._server is not None
    port = listener._server.sockets[0].getsockname()[1]
    return listener, port, devices, telemetry


@pytest.mark.asyncio
async def test_tcp_dispatch_decode_persist_and_ack_end_to_end() -> None:
    listener, port, devices, telemetry = await start_runtime()
    reader = writer = None
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)

        # Identification arrives in separate TCP reads; it must be reassembled.
        writer.write(IMEI_FRAME[:5])
        await writer.drain()
        writer.write(IMEI_FRAME[5:])
        await writer.drain()
        assert await asyncio.wait_for(reader.readexactly(1), timeout=1) == b"\x01"

        frame = codec8_frame()
        # AVL framing must also survive fragmented TCP reads.
        writer.write(frame[:9])
        await writer.drain()
        writer.write(frame[9:])
        await writer.drain()
        assert await asyncio.wait_for(reader.readexactly(4), timeout=1) == b"\x00\x00\x00\x01"

        assert devices.detected_protocols == [(7, "teltonika")]
        assert len(telemetry.saved) == 1
        records, protocol, raw_payload = telemetry.saved[0]
        assert protocol == "teltonika"
        assert raw_payload == frame
        assert len(records) == 1
        assert records[0].device_id == 7
        assert records[0].latitude is not None
        assert records[0].longitude is not None
    finally:
        if writer is not None:
            writer.close()
            await writer.wait_closed()
        await listener.stop()


@pytest.mark.asyncio
async def test_tcp_end_to_end_does_not_ack_avl_when_persistence_fails() -> None:
    listener, port, _devices, telemetry = await start_runtime(fail_persistence=True)
    reader = writer = None
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(IMEI_FRAME)
        await writer.drain()
        assert await asyncio.wait_for(reader.readexactly(1), timeout=1) == b"\x01"

        writer.write(codec8_frame())
        await writer.drain()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(reader.readexactly(4), timeout=0.1)
        assert telemetry.saved == []
    finally:
        if writer is not None:
            writer.close()
            await writer.wait_closed()
        await listener.stop()


@pytest.mark.asyncio
async def test_tcp_end_to_end_rejects_unregistered_imei_without_persistence() -> None:
    listener, port, _devices, telemetry = await start_runtime(registered=False)
    reader = writer = None
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(IMEI_FRAME)
        await writer.drain()
        assert await asyncio.wait_for(reader.readexactly(1), timeout=1) == b"\x00"

        writer.write(codec8_frame())
        await writer.drain()
        await asyncio.sleep(0.05)
        assert telemetry.saved == []
    finally:
        if writer is not None:
            writer.close()
            await writer.wait_closed()
        await listener.stop()
