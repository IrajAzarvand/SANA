from unittest.mock import Mock

from app.protocols.gt06 import crc16_itu
from app.protocols.gt06_handler import GT06Handler
from app.repositories.device import DeviceRecord
from app.transport.session import Session, TransportType


def make_frame(protocol: int, information: bytes = b"", serial: int = 1) -> bytes:
    body = bytes([protocol]) + information + serial.to_bytes(2, "big")
    length_byte = bytes([len(body) + 2])
    checksum = crc16_itu(length_byte + body).to_bytes(2, "big")
    return b"\x78\x78" + length_byte + body + checksum + b"\x0D\x0A"


def active_session() -> Session:
    session = Session(transport=TransportType.TCP, remote_address=("127.0.0.1", 50000))
    session.connect()
    session.activate()
    return session


async def test_gt06_login_binds_registered_device_and_acknowledges():
    device_repository = Mock()
    device_repository.find_by_imei.return_value = DeviceRecord(
        id=9,
        imei="9176515406",
        management_status="active",
        protocol="",
        data_active=True,
    )
    positions = Mock()
    handler = GT06Handler(device_repository, positions)
    session = active_session()
    login_information = bytes.fromhex("0000009176515406")

    response = await handler.handle(session, make_frame(0x01, login_information, 11))

    assert session.device_id == 9
    assert session.device_imei == "9176515406"
    assert response is not None
    assert response.data[3] == 0x01
    device_repository.set_detected_protocol.assert_called_once_with(9, "gt06")


async def test_gt06_position_is_persisted_after_login():
    device_repository = Mock()
    device_repository.find_by_imei.return_value = DeviceRecord(
        id=9,
        imei="9176515406",
        management_status="active",
        protocol="gt06",
        data_active=True,
    )
    positions = Mock()
    handler = GT06Handler(device_repository, positions)
    session = active_session()

    await handler.handle(
        session,
        make_frame(0x01, bytes.fromhex("0000009176515406"), 1),
    )
    info = bytes([26, 10, 10, 12, 30, 45, 8])
    info += int(30 * 1_800_000).to_bytes(4, "big")
    info += int(50 * 1_800_000).to_bytes(4, "big")
    info += bytes([60]) + (0x0C00 | 87).to_bytes(2, "big")
    frame = make_frame(0x12, info, 2)

    response = await handler.handle(session, frame)

    assert response is not None
    assert response.data[3] == 0x12
    positions.save.assert_called_once()
    saved = positions.save.call_args.kwargs
    assert saved["device_id"] == 9
    assert saved["position"].latitude == 30
    assert saved["position"].longitude == 50
    assert saved["raw_frame"] == frame
