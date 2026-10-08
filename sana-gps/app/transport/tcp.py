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
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._session = session
        self._on_data = on_data
        self._closed = False

    @property
    def session(self) -> Session:
        return self._session

    async def run(self) -> None:
        self._session.connect()
        self._session.activate()

        try:
            while not self._reader.at_eof():
                data = await self._reader.read(4096)
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
        await self._writer.wait_closed()


class TCPListener:
    """Accepts TCP connections and creates a runtime session per client."""

    def __init__(
        self,
        host: str,
        port: int,
        session_manager: SessionManager,
        on_data: ConnectionHandler,
    ) -> None:
        self._host = host
        self._port = port
        self._session_manager = session_manager
        self._on_data = on_data
        self._server: asyncio.AbstractServer | None = None
        self._connections: set[asyncio.Task[None]] = set()

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

        self._server.close()
        await self._server.wait_closed()
        self._server = None

        connections = tuple(self._connections)
        if connections:
            await asyncio.gather(*connections, return_exceptions=True)
        self._session_manager.clear_closed()

    async def _accept_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
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

        task = asyncio.create_task(
            self._run_connection(reader, writer, session)
        )
        self._connections.add(task)
        task.add_done_callback(self._connections.discard)

    async def _run_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        session: Session,
    ) -> None:
        connection = TCPConnection(
            reader=reader,
            writer=writer,
            session=session,
            on_data=self._on_data,
        )
        await connection.run()

        self._session_manager.remove(session.id)

    @staticmethod
    def _is_address(value: object) -> bool:
        return (
            isinstance(value, tuple)
            and len(value) >= 2
            and isinstance(value[0], str)
            and isinstance(value[1], int)
        )
