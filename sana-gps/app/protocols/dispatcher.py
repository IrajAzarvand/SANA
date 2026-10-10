from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
from dataclasses import dataclass, field
from uuid import UUID

from app.protocols.types import ProtocolId, ProtocolResponse
from app.transport.session import Session, SessionState


logger = logging.getLogger(__name__)


ProtocolHandler = Callable[
    [Session, bytes],
    Awaitable[ProtocolResponse | None],
]


@dataclass(slots=True)
class _DispatchState:
    session: Session
    protocol: ProtocolId | None = None
    pending: bytearray = field(default_factory=bytearray)
    rejected: bool = False


class ProtocolDispatcher:
    """Detects a TCP GPS protocol once per connection and routes its stream.

    Teltonika starts with a two-byte length-prefixed 15-digit IMEI handshake
    (00 0F); GT06-family frames start with 78 78 or 79 79. Each connection is
    pinned to its first detected protocol so payloads are never passed between
    unrelated decoders.
    """

    _SIGNATURES = {
        b"\x78\x78": ProtocolId.GT06,
        b"\x79\x79": ProtocolId.GT06,
        b"\x00\x0f": ProtocolId.TELTONIKA,
    }

    def __init__(
        self,
        handlers: dict[ProtocolId, ProtocolHandler],
        *,
        max_detection_buffer: int = 8192,
    ) -> None:
        if max_detection_buffer < 2:
            raise ValueError("max_detection_buffer must be at least 2")
        self._handlers = dict(handlers)
        self._max_detection_buffer = max_detection_buffer
        self._states: dict[UUID, _DispatchState] = {}

    async def handle(
        self,
        session: Session,
        data: bytes,
    ) -> ProtocolResponse | None:
        self._cleanup_closed_sessions()
        state = self._states.get(session.id)
        if state is None:
            state = _DispatchState(session=session)
            self._states[session.id] = state

        if state.rejected:
            return None

        if state.protocol is not None:
            handler = self._handlers.get(state.protocol)
            if handler is None:
                state.rejected = True
                return ProtocolResponse(b"\x00")
            return await handler(session, data)

        state.pending.extend(data)
        if len(state.pending) > self._max_detection_buffer:
            state.pending.clear()
            state.rejected = True
            return ProtocolResponse(b"\x00")

        if len(state.pending) < 2:
            return None

        prefix = bytes(state.pending[:2])
        protocol = self._detect(prefix)
        if protocol is None:
            logger.warning(
                "Rejected TCP GPS connection from %s: unknown protocol prefix %s",
                session.remote_address,
                prefix.hex(),
            )
            state.pending.clear()
            state.rejected = True
            return ProtocolResponse(b"\x00")

        logger.info(
            "Detected GPS protocol %s from %s",
            protocol.value,
            session.remote_address,
        )
        state.protocol = protocol
        handler = self._handlers.get(protocol)
        payload = bytes(state.pending)
        state.pending.clear()

        if handler is None:
            state.rejected = True
            return ProtocolResponse(b"\x00")

        return await handler(session, payload)

    @classmethod
    def _detect(cls, prefix: bytes) -> ProtocolId | None:
        return cls._SIGNATURES.get(prefix)

    def _cleanup_closed_sessions(self) -> None:
        closed_ids = [
            session_id
            for session_id, state in self._states.items()
            if state.session.state is SessionState.CLOSED
        ]
        for session_id in closed_ids:
            self._states.pop(session_id, None)
