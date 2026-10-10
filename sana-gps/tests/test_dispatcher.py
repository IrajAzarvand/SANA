from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.protocols.dispatcher import ProtocolDispatcher
from app.protocols.types import ProtocolId, ProtocolResponse
from app.transport.session import Session, TransportType


def make_session() -> Session:
    session = Session(
        transport=TransportType.TCP,
        remote_address=("127.0.0.1", 50000),
    )
    session.connect()
    session.activate()
    return session


@pytest.mark.asyncio
async def test_dispatcher_routes_teltonika_by_identification_prefix():
    teltonika = AsyncMock(return_value=ProtocolResponse(b"\x01"))
    gt06 = AsyncMock(return_value=None)
    dispatcher = ProtocolDispatcher({
        ProtocolId.TELTONIKA: teltonika,
        ProtocolId.GT06: gt06,
    })
    session = make_session()
    handshake = bytes.fromhex("000f333532303934303832313433323533")

    response = await dispatcher.handle(session, handshake)

    assert response == ProtocolResponse(b"\x01")
    teltonika.assert_awaited_once_with(session, handshake)
    gt06.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", [b"\x78\x78", b"\x79\x79"])
async def test_dispatcher_routes_gt06_by_frame_prefix(prefix: bytes):
    teltonika = AsyncMock(return_value=None)
    gt06 = AsyncMock(return_value=ProtocolResponse(b"ack"))
    dispatcher = ProtocolDispatcher({
        ProtocolId.TELTONIKA: teltonika,
        ProtocolId.GT06: gt06,
    })
    session = make_session()
    payload = prefix + b"\x05\x13\x00\x01\x00\x00\x0d\x0a"

    response = await dispatcher.handle(session, payload)

    assert response == ProtocolResponse(b"ack")
    gt06.assert_awaited_once_with(session, payload)
    teltonika.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatcher_buffers_split_protocol_signature():
    teltonika = AsyncMock(return_value=ProtocolResponse(b"\x01"))
    gt06 = AsyncMock(return_value=None)
    dispatcher = ProtocolDispatcher({
        ProtocolId.TELTONIKA: teltonika,
        ProtocolId.GT06: gt06,
    })
    session = make_session()

    assert await dispatcher.handle(session, b"\x00") is None
    assert not teltonika.await_count
    assert not gt06.await_count

    response = await dispatcher.handle(session, b"\x0f123456789012345")

    assert response == ProtocolResponse(b"\x01")
    teltonika.assert_awaited_once_with(session, b"\x00\x0f123456789012345")


@pytest.mark.asyncio
async def test_dispatcher_pins_protocol_for_connection():
    teltonika = AsyncMock(return_value=None)
    gt06 = AsyncMock(return_value=None)
    dispatcher = ProtocolDispatcher({
        ProtocolId.TELTONIKA: teltonika,
        ProtocolId.GT06: gt06,
    })
    session = make_session()

    await dispatcher.handle(session, b"\x78\x78first")
    await dispatcher.handle(session, b"later-data")

    assert gt06.await_count == 2
    teltonika.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatcher_rejects_unknown_protocol_once():
    teltonika = AsyncMock(return_value=None)
    gt06 = AsyncMock(return_value=None)
    dispatcher = ProtocolDispatcher({
        ProtocolId.TELTONIKA: teltonika,
        ProtocolId.GT06: gt06,
    })
    session = make_session()

    response = await dispatcher.handle(session, b"\xaa\xbb")
    later = await dispatcher.handle(session, b"\x78\x78")

    assert response == ProtocolResponse(b"\x00")
    assert later is None
    teltonika.assert_not_awaited()
    gt06.assert_not_awaited()
