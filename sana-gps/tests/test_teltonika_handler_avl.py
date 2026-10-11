from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.protocols.teltonika.decoder import TeltonikaAVLDecoder
from app.protocols.teltonika.handler import TeltonikaHandler
from app.repositories.device import DeviceRecord
from app.transport.session import Session, TransportType


IMEI = "352094082143253"
IMEI_FRAME = bytes.fromhex("000f333532303934303832313433323533")


class FakeDeviceRepository:
    def find_by_imei(self, imei: str) -> DeviceRecord | None:
        if imei != IMEI:
            return None
        return DeviceRecord(
            id=7, imei=IMEI, management_status="warehouse",
            protocol="teltonika", data_active=False,
        )

    def set_detected_protocol(self, device_id: int, protocol: str) -> bool:
        return True


class FakeTelemetryRepository:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.saved = []

    def save_batch(self, records, *, protocol: str, raw_payload: bytes) -> int:
        if self.fail:
            raise RuntimeError("database unavailable")
        self.saved.append((tuple(records), protocol, raw_payload))
        return len(records)


def _codec8_frame() -> bytes:
    timestamp = int(datetime(2026, 10, 10, 12, 4, 57, tzinfo=timezone.utc).timestamp() * 1000)
    record = (
        timestamp.to_bytes(8, "big") + b"\x00"
        + int(459321070).to_bytes(4, "big", signed=True)
        + int(378546450).to_bytes(4, "big", signed=True)
        + int(123).to_bytes(2, "big", signed=True)
        + int(180).to_bytes(2, "big") + b"\x08"
        + int(50).to_bytes(2, "big")
        + bytes((0, 1, 1, 239, 1, 0, 0, 0))
    )
    data = bytes((8, 1)) + record + b"\x01"
    crc = TeltonikaAVLDecoder._crc16_ibm(data)
    return b"\x00\x00\x00\x00" + len(data).to_bytes(4, "big") + data + crc.to_bytes(4, "big")


def _session() -> Session:
    session = Session(transport=TransportType.TCP, remote_address=("127.0.0.1", 19000))
    session.connect()
    session.activate()
    return session


@pytest.mark.asyncio
async def test_avl_batch_is_persisted_before_record_count_ack() -> None:
    repository = FakeTelemetryRepository()
    handler = TeltonikaHandler(FakeDeviceRepository(), repository)
    session = _session()

    login_response = await handler.handle(session, IMEI_FRAME)
    assert login_response is not None and login_response.data == b"\x01"

    response = await handler.handle(session, _codec8_frame())
    assert response is not None and response.data == b"\x00\x00\x00\x01"
    records, protocol, raw = repository.saved[0]
    assert protocol == "teltonika"
    assert raw == _codec8_frame()
    assert len(records) == 1
    assert records[0].device_id == 7
    assert records[0].latitude is not None
    assert records[0].longitude is not None


@pytest.mark.asyncio
async def test_database_failure_does_not_return_successful_avl_ack() -> None:
    handler = TeltonikaHandler(FakeDeviceRepository(), FakeTelemetryRepository(fail=True))
    session = _session()
    await handler.handle(session, IMEI_FRAME)

    response = await handler.handle(session, _codec8_frame())
    assert response is None
