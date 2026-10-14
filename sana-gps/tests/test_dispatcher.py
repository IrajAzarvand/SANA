from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.protocols.dispatcher import ProtocolDispatcher
from app.protocols.types import ProtocolId, ProtocolResponse
from app.transport.session import Session, SessionState, TransportType


def make_session(transport: TransportType = TransportType.TCP) -> Session:
    session = Session(
        transport=transport,
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

@pytest.mark.asyncio
async def test_dispatcher_routes_hq_text_protocol():
    teltonika = AsyncMock(return_value=None)
    gt06 = AsyncMock(return_value=None)
    hq = AsyncMock(return_value=None)
    dispatcher = ProtocolDispatcher({
        ProtocolId.TELTONIKA: teltonika,
        ProtocolId.GT06: gt06,
        ProtocolId.HQ: hq,
    })
    session = make_session()
    payload = b"*HQ,9176515720,V1,112254,A,3751.2787,N,04555.9264,E,0.00,0,101026#"

    await dispatcher.handle(session, payload)

    hq.assert_awaited_once_with(session, payload)
    teltonika.assert_not_awaited()
    gt06.assert_not_awaited()



@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "expected_protocol"),
    [
        (bytes.fromhex("000f333532303934303832313433323533"), ProtocolId.TELTONIKA),
        (bytes.fromhex("78780513000100000d0a"), ProtocolId.GT06),
        (b"*HQ,9176515720,V1,112254,A,3751.2787,N,04555.9264,E,0.00,0,101026#", ProtocolId.HQ),
    ],
)
async def test_dispatcher_routes_udp_by_protocol_signature(payload, expected_protocol):
    handlers = {
        protocol: AsyncMock(return_value=ProtocolResponse(b"ack"))
        for protocol in (ProtocolId.TELTONIKA, ProtocolId.GT06, ProtocolId.HQ)
    }
    dispatcher = ProtocolDispatcher(handlers)
    session = make_session(TransportType.UDP)

    response = await dispatcher.handle(session, payload)

    assert response == ProtocolResponse(b"ack")
    handlers[expected_protocol].assert_awaited_once_with(session, payload)
    for protocol, handler in handlers.items():
        if protocol is not expected_protocol:
            handler.assert_not_awaited()

@pytest.mark.asyncio
@pytest.mark.parametrize("close_state", ["closing", "closed"])
async def test_dispatcher_ignores_data_after_session_starts_closing(close_state):
    teltonika = AsyncMock(return_value=ProtocolResponse(b"\\x01"))
    dispatcher = ProtocolDispatcher({ProtocolId.TELTONIKA: teltonika})
    session = make_session()
    if close_state == "closed":
        session.close()
    else:
        # Model a callback racing the transport shutdown transition.
        session.state = SessionState.CLOSING

    response = await dispatcher.handle(
        session,
        bytes.fromhex("000f333532303934303832313433323533"),
    )

    assert response is None
    teltonika.assert_not_awaited()
    assert session.id not in dispatcher._states


@pytest.mark.asyncio
async def test_dispatcher_captures_unknown_chunks_without_rejecting_connection():
    teltonika = AsyncMock(return_value=None)
    captured = []
    dispatcher = ProtocolDispatcher(
        {ProtocolId.TELTONIKA: teltonika},
        unknown_data_handler=lambda session, payload: captured.append((session.id, payload)),
    )
    session = make_session()

    first_response = await dispatcher.handle(session, b"\xaa\xbbfirst")
    later_response = await dispatcher.handle(session, b"later-packet")

    assert first_response is None
    assert later_response is None
    assert captured == [(session.id, b"\xaa\xbbfirst"), (session.id, b"later-packet")]
    teltonika.assert_not_awaited()
