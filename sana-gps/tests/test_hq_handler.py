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
