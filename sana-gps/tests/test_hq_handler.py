from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.protocols.hq_handler import HQHandler
from app.protocols.types import ProtocolId
from app.repositories.device import DeviceRecord
from app.transport.session import Session, TransportType


def make_session() -> Session:
    session = Session(transport=TransportType.TCP, remote_address=("127.0.0.1", 12345))
    session.connect()
    session.activate()
    return session


@pytest.mark.asyncio
async def test_hq_report_matches_registered_identifier_and_saves_telemetry():
    devices = Mock()
    devices.find_by_imei.return_value = DeviceRecord(
        id=4, imei="9176515720", management_status="warehouse",
        protocol="", data_active=False,
    )
    telemetry = Mock()
    handler = HQHandler(devices, telemetry)
    session = make_session()
    payload = b"*HQ,9176515720,V1,112254,A,3751.2787,N,04555.9264,E,0.00,0,101026,ffffffbff,432,11,3412,10349#"

    await handler.handle(session, payload)

    devices.find_by_imei.assert_called_once_with("9176515720")
    devices.set_detected_protocol.assert_called_once_with(4, "hq*")
    assert session.device_id == 4
    assert session.protocol is ProtocolId.HQ
    telemetry.save.assert_called_once()
    kwargs = telemetry.save.call_args.kwargs
    assert kwargs["device_id"] == 4
    assert kwargs["protocol"] == "hq*"
    assert abs(kwargs["latitude"] - (37 + 51.2787 / 60)) < 0.000001
    assert abs(kwargs["longitude"] - (45 + 55.9264 / 60)) < 0.000001
    assert kwargs["raw_payload"] == payload


@pytest.mark.asyncio
async def test_hq_report_is_buffered_across_tcp_reads():
    devices = Mock()
    devices.find_by_imei.return_value = DeviceRecord(
        id=4, imei="9176515720", management_status="lost",
        protocol="", data_active=False,
    )
    telemetry = Mock()
    handler = HQHandler(devices, telemetry)
    session = make_session()
    first = b"*HQ,9176515720,V1,112254,A,3751.2787,N,04555.9264,E,0.00,0,101026,"
    second = b"ffffffbff,432,11,3412,10349#"

    await handler.handle(session, first)
    telemetry.save.assert_not_called()
    await handler.handle(session, second)

    telemetry.save.assert_called_once()
    assert session.device_id == 4



@pytest.mark.asyncio
async def test_h02_non_position_message_is_saved_without_discarding_fields():
    devices = Mock()
    devices.find_by_imei.return_value = DeviceRecord(
        id=4, imei="9176515720", management_status="active",
        protocol="hq*", data_active=True,
    )
    telemetry = Mock()
    handler = HQHandler(devices, telemetry)
    session = make_session()
    payload = b"*HQ,9176515720,LINK,180902,15,0,84,0,0,240517,FFFFFBFF#"

    await handler.handle(session, payload)

    telemetry.save.assert_called_once()
    saved = telemetry.save.call_args.kwargs
    assert saved["raw_payload"] == payload
    assert saved["gps_valid"] is False
    assert saved["latitude"] is None
    assert saved["attributes"]["h02"]["message_type"] == "LINK"
    assert saved["attributes"]["h02"]["raw_fields"][-1] == "FFFFFBFF"



@pytest.mark.asyncio
async def test_h02_binary_position_frame_is_decoded_and_retained():
    devices = Mock()
    device = DeviceRecord(
        id=4, imei="9176515720", management_status="active",
        protocol="hq*", data_active=True,
    )
    devices.find_by_imei.side_effect = lambda value: device if value == device.imei else None
    telemetry = Mock()
    handler = HQHandler(devices, telemetry)
    session = make_session()
    payload = (
        b"$"
        + bytes.fromhex("9176515720")
        + bytes.fromhex("112254101026")
        + bytes.fromhex("37512787")
        + b"\x03"
        + bytes.fromhex("0455592640")
        + b"\x0e"
        + bytes.fromhex("0000")
        + bytes.fromhex("000000")
        + bytes.fromhex("ffffffff")
    )
    assert len(payload) == 32

    await handler.handle(session, payload)

    telemetry.save.assert_called_once()
    saved = telemetry.save.call_args.kwargs
    assert saved["raw_payload"] == payload
    assert saved["gps_valid"] is True
    assert abs(saved["latitude"] - (37 + 51.2787 / 60)) < 0.000001
    assert abs(saved["longitude"] - (45 + 55.9264 / 60)) < 0.000001
    assert saved["attributes"]["h02"]["message_format"] == "binary"
