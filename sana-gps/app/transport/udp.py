from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from app.transport.session import Session, SessionManager, TransportType


DatagramHandler = Callable[[Session, bytes], Awaitable[None]]
Address = tuple[str, int]


class UDPListener:
    """Receives UDP datagrams and associates them with runtime sessions."""

    def __init__(
        self,
        host: str,
        port: int,
        session_manager: SessionManager,
        on_datagram: DatagramHandler,
    ) -> None:
        self._host = host
        self._port = port
        self._session_manager = session_manager
        self._on_datagram = on_datagram
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol: _UDPProtocol | None = None
        self._receive_task: asyncio.Task[None] | None = None
        self._sessions_by_endpoint: dict[Address, Session] = {}

    async def start(self) -> None:
        if self._transport is not None:
            return

        loop = asyncio.get_running_loop()
        protocol = _UDPProtocol(self)
        transport, _ = await loop.create_datagram_endpoint(
            lambda: protocol,
            local_addr=(self._host, self._port),
        )

        self._protocol = protocol
        self._transport = transport

    async def stop(self) -> None:
        transport = self._transport
        if transport is None:
            return

        self._transport = None
        self._protocol = None

        transport.close()

        for session in tuple(self._sessions_by_endpoint.values()):
            session.close()

        self._sessions_by_endpoint.clear()
        self._session_manager.clear_closed()

    async def _handle_datagram(
        self,
        data: bytes,
        address: object,
    ) -> None:
        if not self._is_address(address):
            return

        session = self._sessions_by_endpoint.get(address)
        if session is None or session.state.value == "closed":
            session = self._session_manager.create(
                transport=TransportType.UDP,
                remote_address=address,
            )
            session.connect()
            session.activate()
            self._sessions_by_endpoint[address] = session

        session.activity()
        await self._on_datagram(session, data)

    @staticmethod
    def _is_address(value: object) -> bool:
        return (
            isinstance(value, tuple)
            and len(value) >= 2
            and isinstance(value[0], str)
            and isinstance(value[1], int)
        )


class _UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, listener: UDPListener) -> None:
        self._listener = listener
        self._loop_task: asyncio.Task[None] | None = None

    def connection_made(
        self,
        transport: asyncio.BaseTransport,
    ) -> None:
        if not isinstance(transport, asyncio.DatagramTransport):
            raise TypeError("Expected asyncio.DatagramTransport")

    def datagram_received(
        self,
        data: bytes,
        addr: tuple[str, int],
    ) -> None:
        task = asyncio.create_task(
            self._listener._handle_datagram(data, addr)
        )
        task.add_done_callback(self._consume_task_exception)

    def error_received(self, exc: Exception) -> None:
        # Transport errors are surfaced by the event loop; no protocol logic
        # belongs in the transport layer.
        return

    def connection_lost(self, exc: Exception | None) -> None:
        return

    @staticmethod
    def _consume_task_exception(task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            # The listener will gain structured logging/error handling in a
            # later stage. For now, avoid leaking task exceptions.
            pass
