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
UnknownDataHandler = Callable[[Session, bytes], None]

# These signatures identify common non-GPS traffic on an exposed TCP port.
# Keep this list conservative: arbitrary binary/ASCII payloads must still be
# eligible for the durable unknown-GPS queue so future tracker protocols survive.
_NON_GPS_PREFIXES = (
    b"GET ",
    b"POST ",
    b"HEAD ",
    b"PUT ",
    b"DELETE ",
    b"OPTIONS ",
    b"PATCH ",
    b"CONNECT ",
    b"TRACE ",
    b"PRI * HTTP/2.0",
    b"HTTP/1.",
    b"HTTP/2",
    b"\x16\x03",  # TLS handshake record
    b"\x17\x03",  # TLS application-data record
    b"SSH-",
)


def _is_obvious_non_gps_traffic(data: bytes) -> bool:
    """Return true only for recognizable HTTP/TLS/SSH protocol signatures."""
    return any(data.startswith(prefix) for prefix in _NON_GPS_PREFIXES)


def _may_be_non_gps_prefix(data: bytes) -> bool:
    """Buffer partial signatures (e.g. 'G', then 'ET ') across TCP reads."""
    return any(prefix.startswith(data) for prefix in _NON_GPS_PREFIXES)


@dataclass(slots=True)
class _DispatchState:
    session: Session
    protocol: ProtocolId | None = None
    pending: bytearray = field(default_factory=bytearray)
    rejected: bool = False
    unknown: bool = False


class ProtocolDispatcher:
    """Detect and pin a protocol, with an optional bounded unknown-data capture hook."""

    def __init__(
        self,
        handlers: dict[ProtocolId, ProtocolHandler],
        *,
        registry: ProtocolRegistry | None = None,
        max_detection_buffer: int = 8192,
        unknown_data_handler: UnknownDataHandler | None = None,
    ) -> None:
        if max_detection_buffer < 2:
            raise ValueError("max_detection_buffer must be at least 2")
        self._handlers = dict(handlers)
        self._registry = registry or default_protocol_registry()
        self._max_detection_buffer = max_detection_buffer
        self._unknown_data_handler = unknown_data_handler
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
        if state.unknown:
            self._capture_unknown(session, data)
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
            # Discard clearly identifiable internet scan traffic before it can
            # reach durable storage. Do not reply with a GPS-specific ACK.
            if _is_obvious_non_gps_traffic(pending):
                logger.info(
                    "Ignoring non-GPS TCP traffic from %s (signature=%s)",
                    session.remote_address,
                    pending[:16].hex(),
                )
                state.pending.clear()
                state.rejected = True
                return None

            # A method/signature may be split across multiple TCP reads. Keep
            # short possible prefixes in memory until they can be classified.
            if (
                self._registry.may_match_prefix(pending)
                or _may_be_non_gps_prefix(pending)
                or len(pending) < 2
            ):
                return None

            if self._unknown_data_handler is not None:
                # Preserve raw bytes for investigation and keep accepting
                # bounded chunks; do not send a protocol-specific rejection ACK.
                state.unknown = True
                state.pending.clear()
                self._capture_unknown(session, pending)
                logger.info("Captured unknown GPS protocol sample from %s (%d bytes)",
                            session.remote_address, len(pending))
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

    def _capture_unknown(self, session: Session, payload: bytes) -> None:
        if self._unknown_data_handler is None or not payload:
            return
        try:
            self._unknown_data_handler(session, payload)
        except Exception:
            # Capture/investigation must never crash the transport callback.
            logger.exception("Failed to capture unknown GPS data from %s", session.remote_address)

    def _cleanup_closed_sessions(self) -> None:
        closed_ids = [sid for sid, state in self._states.items()
                      if state.session.state is SessionState.CLOSED]
        for sid in closed_ids:
            self._states.pop(sid, None)
