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


@pytest.mark.asyncio
async def test_transport_server_integrates_tcp_and_udp_sessions() -> None:
    manager = SessionManager()
    received: list[tuple[str, object, bytes]] = []
    received_event = asyncio.Event()

    async def on_data(session, data: bytes) -> None:
        received.append((session.transport.value, session, data))
        if len(received) == 4:
            received_event.set()

    server = TransportServer(
        "127.0.0.1",
        0,
        0,
        manager,
        on_data,
        tcp_idle_timeout=1.0,
        udp_session_timeout=1.0,
        max_tcp_connections=2,
        max_udp_sessions=2,
        max_datagram_size=64,
    )
    await server.start()

    tcp_writers = []
    udp_clients = []
    try:
        tcp_port = server._tcp_listener._server.sockets[0].getsockname()[1]
        udp_address = server._udp_listener._transport.get_extra_info("sockname")

        for payload in (b"tcp-a", b"tcp-b"):
            _, writer = await asyncio.open_connection("127.0.0.1", tcp_port)
            writer.write(payload)
            await writer.drain()
            tcp_writers.append(writer)

        loop = asyncio.get_running_loop()
        for payload in (b"udp-a", b"udp-b"):
            client, _ = await loop.create_datagram_endpoint(
                asyncio.DatagramProtocol, remote_addr=udp_address
            )
            client.sendto(payload)
            udp_clients.append(client)

        await asyncio.wait_for(received_event.wait(), timeout=1.0)

        assert sorted((kind, data) for kind, _, data in received) == [
            ("tcp", b"tcp-a"),
            ("tcp", b"tcp-b"),
            ("udp", b"udp-a"),
            ("udp", b"udp-b"),
        ]
        assert len({session.id for _, session, _ in received}) == 4
    finally:
        for writer in tcp_writers:
            writer.close()
            await writer.wait_closed()
        for client in udp_clients:
            client.close()
        await server.stop()

    assert manager.active_count() == 0


@pytest.mark.asyncio
async def test_transport_server_restart_has_clean_transport_state() -> None:
    manager = SessionManager()
    received = asyncio.Event()

    async def on_data(session, data: bytes) -> None:
        received.set()

    server = TransportServer("127.0.0.1", 0, 0, manager, on_data)

    await server.start()
    first_tcp_port = server._tcp_listener._server.sockets[0].getsockname()[1]
    await server.stop()

    assert manager.active_count() == 0

    await server.start()
    try:
        second_tcp_port = server._tcp_listener._server.sockets[0].getsockname()[1]
        assert second_tcp_port != first_tcp_port or second_tcp_port > 0

        _, writer = await asyncio.open_connection("127.0.0.1", second_tcp_port)
        try:
            writer.write(b"restart")
            await writer.drain()
            await asyncio.wait_for(received.wait(), timeout=1.0)
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await server.stop()

    assert manager.active_count() == 0


@pytest.mark.asyncio
async def test_transport_server_delivers_gt06_tcp_data_separately():
    manager = SessionManager()
    regular_received = []
    gt06_received = []
    gt06_event = asyncio.Event()

    async def on_data(session, data):
        regular_received.append(data)

    async def on_gt06_data(session, data):
        gt06_received.append(data)
        gt06_event.set()

    server = TransportServer(
        "127.0.0.1", 0, 0, manager, on_data,
        gt06_tcp_port=0, gt06_on_data=on_gt06_data,
    )
    await server.start()
    try:
        regular_port = server._tcp_listener._server.sockets[0].getsockname()[1]
        gt06_port = server._gt06_tcp_listener._server.sockets[0].getsockname()[1]

        _, regular_writer = await asyncio.open_connection("127.0.0.1", regular_port)
        _, gt06_writer = await asyncio.open_connection("127.0.0.1", gt06_port)
        try:
            regular_writer.write(b"teltonika-path")
            gt06_writer.write(b"gt06-path")
            await regular_writer.drain()
            await gt06_writer.drain()
            await asyncio.wait_for(gt06_event.wait(), timeout=1.0)
            await asyncio.sleep(0.05)
        finally:
            regular_writer.close()
            gt06_writer.close()
            await regular_writer.wait_closed()
            await gt06_writer.wait_closed()

        assert regular_received == [b"teltonika-path"]
        assert gt06_received == [b"gt06-path"]
    finally:
        await server.stop()
