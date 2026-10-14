from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
from dataclasses import dataclass, field
from uuid import UUID

from app.protocols.registry import ProtocolRegistry, default_protocol_registry
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
    """Detect and pin a protocol using the shared registry, then route to its handler."""

    def __init__(
        self,
        handlers: dict[ProtocolId, ProtocolHandler],
        *,
        registry: ProtocolRegistry | None = None,
        max_detection_buffer: int = 8192,
    ) -> None:
        if max_detection_buffer < 2:
            raise ValueError("max_detection_buffer must be at least 2")
        self._handlers = dict(handlers)
        self._registry = registry or default_protocol_registry()
        self._max_detection_buffer = max_detection_buffer
        self._states: dict[UUID, _DispatchState] = {}

    async def handle(self, session: Session, data: bytes) -> ProtocolResponse | None:
        self._cleanup_closed_sessions()
        # A delayed read/callback must not create dispatcher state or invoke a
        # protocol handler after its transport session has begun closing.
        if session.state in {SessionState.CLOSING, SessionState.CLOSED}:
            return None

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

        # Detection is delegated to the registry. Incomplete signatures remain
        # buffered instead of being rejected before the next TCP read arrives.
        pending = bytes(state.pending)
        detection = self._registry.detect(pending)
        if not detection.matched:
            if self._registry.may_match_prefix(pending) or len(pending) < 2:
                return None
            logger.warning("Rejected TCP GPS connection from %s: unknown protocol prefix %s",
                           session.remote_address, pending[:8].hex())
            state.pending.clear()
            state.rejected = True
            return ProtocolResponse(b"\x00")

        protocol = detection.protocol
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
