from __future__ import annotations

import asyncio

import pytest

from app.transport.session import SessionManager, SessionState, TransportType
from app.transport.udp import UDPListener


@pytest.mark.asyncio
async def test_udp_listener_receives_datagram_and_reuses_session() -> None:
    manager = SessionManager()
    received: list[tuple[object, bytes]] = []
    received_event = asyncio.Event()

    async def on_datagram(session, data: bytes) -> None:
        received.append((session, data))
        if len(received) == 2:
            received_event.set()

    listener = UDPListener("127.0.0.1", 0, manager, on_datagram)
    await listener.start()

    try:
        assert listener._transport is not None
        address = listener._transport.get_extra_info("sockname")

        transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
            asyncio.DatagramProtocol,
            remote_addr=address,
        )
        try:
            transport.sendto(b"hello")
            transport.sendto(b"world")
            await asyncio.wait_for(received_event.wait(), timeout=1.0)
        finally:
            transport.close()

        assert len(received) == 2
        assert received[0][1] == b"hello"
        assert received[1][1] == b"world"
        assert received[0][0] is received[1][0]

        session = received[0][0]
        assert session.transport is TransportType.UDP
        assert session.state is SessionState.ACTIVE
        assert manager.active_count() == 1
    finally:
        await listener.stop()


@pytest.mark.asyncio
async def test_udp_listener_creates_independent_sessions_for_endpoints() -> None:
    manager = SessionManager()
    sessions: list[object] = []
    received_event = asyncio.Event()

    async def on_datagram(session, data: bytes) -> None:
        sessions.append(session)
        if len(sessions) == 2:
            received_event.set()

    listener = UDPListener("127.0.0.1", 0, manager, on_datagram)
    await listener.start()

    try:
        assert listener._transport is not None
        address = listener._transport.get_extra_info("sockname")
        loop = asyncio.get_running_loop()

        transport_a, _ = await loop.create_datagram_endpoint(
            asyncio.DatagramProtocol,
            local_addr=("127.0.0.1", 0),
            remote_addr=address,
        )
        transport_b, _ = await loop.create_datagram_endpoint(
            asyncio.DatagramProtocol,
            local_addr=("127.0.0.1", 0),
            remote_addr=address,
        )

        try:
            transport_a.sendto(b"a")
            transport_b.sendto(b"b")
            await asyncio.wait_for(received_event.wait(), timeout=1.0)
        finally:
            transport_a.close()
            transport_b.close()

        assert sessions[0] is not sessions[1]
        assert manager.active_count() == 2
    finally:
        await listener.stop()


@pytest.mark.asyncio
async def test_udp_listener_stop_is_idempotent_and_can_restart() -> None:
    manager = SessionManager()
    received_event = asyncio.Event()

    async def on_datagram(session, data: bytes) -> None:
        received_event.set()

    listener = UDPListener("127.0.0.1", 0, manager, on_datagram)

    await listener.start()
    await listener.stop()
    await listener.stop()

    await listener.start()
    try:
        assert listener._transport is not None
        address = listener._transport.get_extra_info("sockname")
        transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
            asyncio.DatagramProtocol,
            remote_addr=address,
        )
        try:
            transport.sendto(b"restart")
            await asyncio.wait_for(received_event.wait(), timeout=1.0)
        finally:
            transport.close()
    finally:
        await listener.stop()

    assert manager.active_count() == 0
