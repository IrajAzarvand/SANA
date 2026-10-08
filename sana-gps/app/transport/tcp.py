from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from app.transport.session import Session, SessionManager, TransportType


ConnectionHandler = Callable[[Session, bytes], Awaitable[None]]


class TCPConnection:
    """Owns one TCP client connection and its runtime session."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        session: Session,
        on_data: ConnectionHandler,
        idle_timeout: float,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._session = session
        self._on_data = on_data
        self._idle_timeout = idle_timeout
        self._closed = False

    @property
    def session(self) -> Session:
        return self._session

    async def run(self) -> None:
        self._session.connect()
        self._session.activate()

        try:
            while not self._reader.at_eof():
                try:
                    data = await asyncio.wait_for(
                        self._reader.read(4096),
                        timeout=self._idle_timeout,
                    )
                except asyncio.TimeoutError:
                    break

                if not data:
                    break

                self._session.activity()
                await self._on_data(self._session, data)
        finally:
            await self.close()

    async def close(self) -> None:
        if self._closed:
            return

        self._closed = True
        self._session.close()
        self._writer.close()
        try:
            await asyncio.wait_for(self._writer.wait_closed(), timeout=1.0)
        except asyncio.TimeoutError:
            pass


class TCPListener:
    """Accepts TCP connections and creates a runtime session per client."""

    def __init__(
        self,
        host: str,
        port: int,
        session_manager: SessionManager,
        on_data: ConnectionHandler,
        *,
        idle_timeout: float = 300.0,
        max_connections: int = 100,
    ) -> None:
        self._host = host
        self._port = port
        self._session_manager = session_manager
        self._on_data = on_data
        self._idle_timeout = idle_timeout
        self._max_connections = max_connections
        self._server: asyncio.AbstractServer | None = None
        self._connections: dict[asyncio.Task[None], TCPConnection] = {}

    async def start(self) -> None:
        if self._server is not None:
            return

        self._server = await asyncio.start_server(
            self._accept_client,
            host=self._host,
            port=self._port,
        )

    async def stop(self) -> None:
        if self._server is None:
            return

        server = self._server
        server.close()
        self._server = None

        tasks = tuple(self._connections)
        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        await server.wait_closed()
        self._session_manager.clear_closed()

    async def _accept_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        if len(self._connections) >= self._max_connections:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), timeout=1.0)
            except asyncio.TimeoutError:
                pass
            return

        peer = writer.get_extra_info("peername")
        local = writer.get_extra_info("sockname")

        if not self._is_address(peer):
            writer.close()
            await writer.wait_closed()
            return

        session = self._session_manager.create(
            transport=TransportType.TCP,
            remote_address=peer,
            local_address=local if self._is_address(local) else None,
        )

        connection = TCPConnection(
            reader,
            writer,
            session,
            self._on_data,
            self._idle_timeout,
        )
        task = asyncio.create_task(self._run_connection(connection))
        self._connections[task] = connection
        task.add_done_callback(self._connection_task_done)

    async def _run_connection(self, connection: TCPConnection) -> None:
        try:
            await connection.run()
        finally:
            self._session_manager.remove(connection.session.id)

    @staticmethod
    def _is_address(value: object) -> bool:
        return (
            isinstance(value, tuple)
            and len(value) >= 2
            and isinstance(value[0], str)
            and isinstance(value[1], int)
        )
