import asyncio

import pytest

from app.protocols.types import ProtocolResponse
from app.transport.session import SessionManager
from app.transport.tcp import TCPListener
from app.transport.udp import UDPListener


@pytest.mark.asyncio
async def test_tcp_listener_sends_handler_response() -> None:
    manager = SessionManager()

    async def on_data(session, data):
        return ProtocolResponse(data=b"01")

    listener = TCPListener("127.0.0.1", 0, manager, on_data)
    await listener.start()
    port = listener._server.sockets[0].getsockname()[1]

    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"hello")
    await writer.drain()

    assert await asyncio.wait_for(reader.readexactly(2), timeout=1) == b"01"

    writer.close()
    await writer.wait_closed()
    await listener.stop()


@pytest.mark.asyncio
async def test_udp_listener_sends_handler_response() -> None:
    manager = SessionManager()

    async def on_datagram(session, data):
        return ProtocolResponse(data=b"01")

    listener = UDPListener("127.0.0.1", 0, manager, on_datagram)
    await listener.start()
    port = listener._transport.get_extra_info("sockname")[1]

    loop = asyncio.get_running_loop()
    received = loop.create_future()

    class ClientProtocol(asyncio.DatagramProtocol):
        def datagram_received(self, data, addr):
            if not received.done():
                received.set_result(data)

    transport, _ = await loop.create_datagram_endpoint(
        ClientProtocol,
        local_addr=("127.0.0.1", 0),
    )
    try:
        transport.sendto(b"hello", ("127.0.0.1", port))
        assert await asyncio.wait_for(received, timeout=1) == b"01"
    finally:
        transport.close()
        await listener.stop()
