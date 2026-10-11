from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from app.protocols.types import ProtocolResponse
from app.transport.session import Session, SessionManager, SessionState, TransportType


DatagramHandler = Callable[[Session, bytes], Awaitable[ProtocolResponse | None]]
Address = tuple[str, int]


class UDPListener:
    """Receives UDP datagrams and associates them with runtime sessions."""

    def __init__(
        self,
        host: str,
        port: int,
        session_manager: SessionManager,
        on_datagram: DatagramHandler,
        *,
        session_timeout: float = 300.0,
        max_sessions: int = 10000,
        max_datagram_size: int = 8192,
    ) -> None:
        self._host = host
        self._port = port
        self._session_manager = session_manager
        self._on_datagram = on_datagram
        self._session_timeout = session_timeout
        self._max_sessions = max_sessions
        self._max_datagram_size = max_datagram_size
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol: _UDPProtocol | None = None
        self._handler_tasks: set[asyncio.Task[None]] = set()
        self._sessions_by_endpoint: dict[Address, Session] = {}
        self._endpoint_locks: dict[Address, asyncio.Lock] = {}
        self._cleanup_task: asyncio.Task[None] | None = None

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
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        transport = self._transport
        if transport is None:
            return

        self._transport = None
        self._protocol = None

        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            await asyncio.gather(self._cleanup_task, return_exceptions=True)
            self._cleanup_task = None

        transport.close()

        tasks = tuple(self._handler_tasks)
        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        for session in tuple(self._sessions_by_endpoint.values()):
            session.close()

        self._sessions_by_endpoint.clear()
        self._endpoint_locks.clear()
        self._session_manager.clear_closed()

    async def _cleanup_loop(self) -> None:
        interval = min(max(self._session_timeout / 2, 0.1), 30.0)
        try:
            while True:
                await asyncio.sleep(interval)
                self._expire_idle_sessions()
        except asyncio.CancelledError:
            raise

    def _expire_idle_sessions(self) -> None:
        now = datetime.now(timezone.utc)
        expired = [
            endpoint
            for endpoint, session in self._sessions_by_endpoint.items()
            if (now - session.last_activity_at).total_seconds()
            >= self._session_timeout
        ]

        for endpoint in expired:
            session = self._sessions_by_endpoint.pop(endpoint)
            session.close()
            self._session_manager.remove(session.id)
            lock = self._endpoint_locks.get(endpoint)
            if lock is not None and not lock.locked():
                self._endpoint_locks.pop(endpoint, None)

    async def _handle_datagram(
        self,
        data: bytes,
        address: object,
    ) -> None:
        if not self._is_address(address):
            return

        if len(data) > self._max_datagram_size:
            return

        # Datagram callbacks create tasks independently. A per-endpoint lock
        # preserves arrival order for one sender while unrelated senders can
        # continue processing concurrently.
        lock = self._endpoint_locks.setdefault(address, asyncio.Lock())
        async with lock:
            await self._process_datagram(data, address)

        if address not in self._sessions_by_endpoint:
            current_lock = self._endpoint_locks.get(address)
            if current_lock is lock and not lock.locked():
                self._endpoint_locks.pop(address, None)

    async def _process_datagram(self, data: bytes, address: Address) -> None:
        session = self._sessions_by_endpoint.get(address)
        if session is None or session.state is SessionState.CLOSED:
            if len(self._sessions_by_endpoint) >= self._max_sessions:
                return

            session = self._session_manager.create(
                transport=TransportType.UDP,
                remote_address=address,
            )
            session.connect()
            session.activate()
            self._sessions_by_endpoint[address] = session

        session.activity()
        response = await self._on_datagram(session, data)

        # A different endpoint may have established a newer session for the
        # same registered device while an async handler was in progress.
        if (
            session.device_id is not None
            and not self._session_manager.is_current(session)
        ):
            return

        if response is not None and self._transport is not None:
            self._transport.sendto(response.data, address)

    def _track_handler_task(self, task: asyncio.Task[None]) -> None:
        self._handler_tasks.add(task)
        task.add_done_callback(self._handler_tasks.discard)
        task.add_done_callback(self._consume_task_exception)

    @staticmethod
    def _consume_task_exception(task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            # Structured transport logging will be added with observability.
            # The callback prevents unhandled-task warnings at this stage.
            pass

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

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
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
        self._listener._track_handler_task(task)

    def error_received(self, exc: Exception) -> None:
        # Protocol-specific error handling does not belong in transport.
        return

    def connection_lost(self, exc: Exception | None) -> None:
        return
