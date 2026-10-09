from __future__ import annotations

import pytest

from app.protocols.teltonika.handler import TeltonikaHandler
from app.protocols.types import ProtocolId
from app.repositories.device import DeviceRecord
from app.transport.session import Session, TransportType


IMEI = "352094082143253"
IMEI_FRAME = bytes.fromhex("000f333532303934303832313433323533")


class FakeDeviceRepository:
    def __init__(self, device: DeviceRecord | None) -> None:
        self.device = device
        self.detected_protocols: list[tuple[int, str]] = []

    def find_by_imei(self, imei: str) -> DeviceRecord | None:
        if self.device is not None and self.device.imei == imei:
            return self.device
        return None

    def set_detected_protocol(self, device_id: int, protocol: str) -> bool:
        self.detected_protocols.append((device_id, protocol))
        return True


def _session() -> Session:
    session = Session(
        transport=TransportType.TCP,
        remote_address=("127.0.0.1", 19000),
    )
    session.connect()
    session.activate()
    return session


def _device(*, protocol: str = "teltonika", status: str = "warehouse") -> DeviceRecord:
    return DeviceRecord(
        id=7,
        imei=IMEI,
        management_status=status,
        protocol=protocol,
        data_active=False,
    )


@pytest.mark.asyncio
async def test_registered_teltonika_device_receives_accept_response() -> None:
    handler = TeltonikaHandler(FakeDeviceRepository(_device()))
    session = _session()

    response = await handler.handle(session, IMEI_FRAME)

    assert response is not None
    assert response.data == b"\x01"
    assert session.device_id == 7
    assert session.device_imei == IMEI
    assert session.protocol is ProtocolId.TELTONIKA


@pytest.mark.asyncio
async def test_unknown_protocol_is_detected_and_persisted_from_valid_imei_handshake() -> None:
    repository = FakeDeviceRepository(_device(protocol=""))
    handler = TeltonikaHandler(repository)
    session = _session()

    response = await handler.handle(session, IMEI_FRAME)

    assert response is not None
    assert response.data == b"\\x01"
    assert session.device_id == 7
    assert repository.detected_protocols == [(7, "teltonika")]


@pytest.mark.asyncio
async def test_unknown_device_receives_reject_response() -> None:
    handler = TeltonikaHandler(FakeDeviceRepository(None))
    session = _session()

    response = await handler.handle(session, IMEI_FRAME)

    assert response is not None
    assert response.data == b"\x00"
    assert session.device_id is None


@pytest.mark.asyncio
async def test_wrong_protocol_receives_reject_response() -> None:
    handler = TeltonikaHandler(FakeDeviceRepository(_device(protocol="gt06")))
    session = _session()

    response = await handler.handle(session, IMEI_FRAME)

    assert response is not None
    assert response.data == b"\x00"
    assert session.device_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    ["warehouse", "sold", "installed", "active", "ready", "faulty", "lost", "stolen", "retired", "disposed"],
)
async def test_management_status_does_not_block_handshake(status: str) -> None:
    handler = TeltonikaHandler(FakeDeviceRepository(_device(status=status)))
    session = _session()

    response = await handler.handle(session, IMEI_FRAME)

    assert response is not None
    assert response.data == b"\x01"
    assert session.device_id == 7


@pytest.mark.asyncio
async def test_split_identification_waits_for_complete_frame() -> None:
    handler = TeltonikaHandler(FakeDeviceRepository(_device()))
    session = _session()

    assert await handler.handle(session, IMEI_FRAME[:7]) is None
    response = await handler.handle(session, IMEI_FRAME[7:])

    assert response is not None
    assert response.data == b"\x01"
    assert session.device_id == 7
