import asyncio
from unittest.mock import AsyncMock

import pytest

from app.transport.server import TransportServer
from app.transport.session import SessionManager


@pytest.mark.asyncio
async def test_transport_server_starts_tcp_and_udp():
    manager = SessionManager()

    async def on_data(session, data):
        return None

    server = TransportServer("127.0.0.1", 0, 0, manager, on_data)

    await server.start()
    try:
        assert server._tcp_listener._server is not None
        assert server._udp_listener._transport is not None
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_transport_server_delivers_tcp_and_udp_data():
    manager = SessionManager()
    received: list[tuple[str, bytes]] = []
    event = asyncio.Event()

    async def on_data(session, data):
        received.append((session.transport.value, data))
        if len(received) == 2:
            event.set()

    server = TransportServer("127.0.0.1", 0, 0, manager, on_data)
    await server.start()

    try:
        tcp_server = server._tcp_listener._server
        udp_transport = server._udp_listener._transport
        assert tcp_server is not None
        assert udp_transport is not None

        tcp_port = tcp_server.sockets[0].getsockname()[1]
        udp_address = udp_transport.get_extra_info("sockname")

        _, writer = await asyncio.open_connection("127.0.0.1", tcp_port)
        udp_client, _ = await asyncio.get_running_loop().create_datagram_endpoint(
            asyncio.DatagramProtocol,
            remote_addr=udp_address,
        )

        try:
            writer.write(b"tcp")
            await writer.drain()
            udp_client.sendto(b"udp")
            await asyncio.wait_for(event.wait(), timeout=1.0)
        finally:
            writer.close()
            await writer.wait_closed()
            udp_client.close()

        assert {item for item in received} == {
            ("tcp", b"tcp"),
            ("udp", b"udp"),
        }
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_transport_server_start_failure_cleans_partial_start():
    manager = SessionManager()

    async def on_data(session, data):
        return None

    server = TransportServer("127.0.0.1", 0, 0, manager, on_data)
    server._udp_listener.start = AsyncMock(
        side_effect=OSError("UDP bind failed")
    )

    with pytest.raises(OSError, match="UDP bind failed"):
        await server.start()

    assert server._tcp_listener._server is None
    assert server._udp_listener._transport is None
    assert not server._started


@pytest.mark.asyncio
async def test_transport_server_stop_is_idempotent():
    manager = SessionManager()

    async def on_data(session, data):
        return None

    server = TransportServer("127.0.0.1", 0, 0, manager, on_data)

    await server.stop()
    await server.start()
    await server.stop()
    await server.stop()

    assert server._tcp_listener._server is None
    assert server._udp_listener._transport is None
