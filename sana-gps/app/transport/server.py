from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.transport.session import Session, SessionManager
from app.transport.tcp import TCPListener
from app.transport.udp import UDPListener


TransportDataHandler = Callable[[Session, bytes], Awaitable[None]]


class TransportServer:
    """Owns the TCP and UDP listeners used by the SANA GPS runtime."""

    def __init__(
        self,
        host: str,
        tcp_port: int,
        udp_port: int,
        session_manager: SessionManager,
        on_data: TransportDataHandler,
    ) -> None:
        self._tcp_listener = TCPListener(host, tcp_port, session_manager, on_data)
        self._udp_listener = UDPListener(host, udp_port, session_manager, on_data)
        self._started = False

    async def start(self) -> None:
        if self._started:
            return

        try:
            await self._tcp_listener.start()
            await self._udp_listener.start()
        except Exception:
            await self.stop()
            raise

        self._started = True

    async def stop(self) -> None:
        errors: list[BaseException] = []

        for listener in (self._tcp_listener, self._udp_listener):
            try:
                await listener.stop()
            except BaseException as exc:
                errors.append(exc)

        self._started = False

        if errors:
            raise errors[0]
