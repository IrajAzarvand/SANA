import asyncio

import pytest

from app.transport.session import SessionManager, SessionState, TransportType
from app.transport.tcp import TCPListener


@pytest.mark.asyncio
async def test_tcp_listener_accepts_connection_and_receives_data():
    received: list[tuple[object, bytes]] = []
    data_received = asyncio.Event()

    async def on_data(session, data):
        received.append((session, data))
        data_received.set()

    manager = SessionManager()
    listener = TCPListener("127.0.0.1", 0, manager, on_data)

    await listener.start()
    assert listener._server is not None

    port = listener._server.sockets[0].getsockname()[1]

    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"hello")
    await writer.drain()

    await asyncio.wait_for(data_received.wait(), timeout=1)

    session, data = received[0]
    assert session.transport == TransportType.TCP
    assert session.state == SessionState.ACTIVE
    assert data == b"hello"

    writer.close()
    await writer.wait_closed()
    await listener.stop()

    assert manager.active_count() == 0


@pytest.mark.asyncio
async def test_tcp_listener_creates_independent_sessions():
    sessions = []
    data_received = asyncio.Event()

    async def on_data(session, data):
        sessions.append(session)
        if len(sessions) == 2:
            data_received.set()

    manager = SessionManager()
    listener = TCPListener("127.0.0.1", 0, manager, on_data)

    await listener.start()
    port = listener._server.sockets[0].getsockname()[1]

    writers = []
    for payload in (b"one", b"two"):
        _, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(payload)
        await writer.drain()
        writers.append(writer)

    await asyncio.wait_for(data_received.wait(), timeout=1)

    assert len({session.id for session in sessions}) == 2

    for writer in writers:
        writer.close()
        await writer.wait_closed()

    await listener.stop()


@pytest.mark.asyncio
async def test_tcp_listener_stop_closes_active_connections():
    data_received = asyncio.Event()

    async def on_data(session, data):
        data_received.set()

    manager = SessionManager()
    listener = TCPListener("127.0.0.1", 0, manager, on_data)

    await listener.start()
    port = listener._server.sockets[0].getsockname()[1]

    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"active")
    await writer.drain()

    await asyncio.wait_for(data_received.wait(), timeout=1)
    assert manager.active_count() == 1

    await listener.stop()

    assert manager.active_count() == 0
    assert reader.at_eof() or writer.is_closing()
