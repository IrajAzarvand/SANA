from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
from dataclasses import dataclass, field
from uuid import UUID

from app.protocols.types import ProtocolId, ProtocolResponse
from app.transport.session import Session, SessionState


logger = logging.getLogger(__name__)
ProtocolHandler = Callable[[Session, bytes], Awaitable[ProtocolResponse | None]]


@dataclass(slots=True)
class _DispatchState:
    session: Session
    protocol: ProtocolId | None = None
    pending: bytearray = field(default_factory=bytearray)
    rejected: bool = False


class ProtocolDispatcher:
    """Detect a protocol from buffered bytes, then pin it for the TCP session."""

    _SIGNATURES = {
        b"\x78\x78": ProtocolId.GT06,
        b"\x79\x79": ProtocolId.GT06,
        b"\x00\x0f": ProtocolId.TELTONIKA,
        b"*H": ProtocolId.HQ,
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

    async def handle(self, session: Session, data: bytes) -> ProtocolResponse | None:
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
            logger.warning("Rejecting GPS session from %s: detection buffer limit exceeded", session.remote_address)
            state.pending.clear()
            state.rejected = True
            return ProtocolResponse(b"\x00")

        # Do not reject on an incomplete prefix. Wait for enough bytes to decide.
        pending = bytes(state.pending)
        protocol = next((proto for signature, proto in self._SIGNATURES.items()
                         if pending.startswith(signature)), None)
        if protocol is None:
            possible_prefix = any(signature.startswith(pending) for signature in self._SIGNATURES)
            if possible_prefix or len(pending) < 2:
                return None
            logger.warning("Rejected TCP GPS connection from %s: unknown protocol prefix %s",
                           session.remote_address, pending[:8].hex())
            state.pending.clear()
            state.rejected = True
            return ProtocolResponse(b"\x00")

        logger.info("Detected GPS protocol %s from %s", protocol.value, session.remote_address)
        state.protocol = protocol
        handler = self._handlers.get(protocol)
        payload = bytes(state.pending)
        state.pending.clear()
        if handler is None:
            state.rejected = True
            return ProtocolResponse(b"\x00")
        return await handler(session, payload)

    def _cleanup_closed_sessions(self) -> None:
        closed_ids = [sid for sid, state in self._states.items()
                      if state.session.state is SessionState.CLOSED]
        for sid in closed_ids:
            self._states.pop(sid, None)
