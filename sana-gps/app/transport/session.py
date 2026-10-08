from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from app.protocols.types import ProtocolId


class TransportType(str, Enum):
    TCP = "tcp"
    UDP = "udp"


class SessionState(str, Enum):
    NEW = "new"
    CONNECTED = "connected"
    ACTIVE = "active"
    CLOSING = "closing"
    CLOSED = "closed"


class SessionStateError(RuntimeError):
    """Raised when an invalid session state transition is requested."""


@dataclass(slots=True)
class Session:
    transport: TransportType
    remote_address: tuple[str, int]
    local_address: tuple[str, int] | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_activity_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    state: SessionState = SessionState.NEW
    device_id: int | None = None
    device_imei: str | None = None
    protocol: ProtocolId | None = None
    authenticated_at: datetime | None = None

    def bind_device(
        self,
        *,
        device_id: int,
        imei: str,
        protocol: ProtocolId,
    ) -> None:
        """Bind a runtime session to a registered SANA device."""
        if self.state not in {SessionState.CONNECTED, SessionState.ACTIVE}:
            raise SessionStateError(
                "Session must be CONNECTED or ACTIVE to bind a device"
            )
        if self.device_id is not None:
            raise SessionStateError("Session is already bound to a device")

        self.device_id = device_id
        self.device_imei = imei
        self.protocol = protocol
        self.authenticated_at = datetime.now(timezone.utc)

    def connect(self) -> None:
        self._transition(SessionState.CONNECTED)

    def activate(self) -> None:
        self._transition(SessionState.ACTIVE)

    def activity(self) -> None:
        if self.state != SessionState.ACTIVE:
            raise SessionStateError(
                "Session must be ACTIVE to record activity"
            )

        self.last_activity_at = datetime.now(timezone.utc)

    def close(self) -> None:
        if self.state == SessionState.CLOSED:
            return

        self._transition(SessionState.CLOSING)
        self._transition(SessionState.CLOSED)

    def _transition(self, new_state: SessionState) -> None:
        valid_transitions = {
            SessionState.NEW: {
                SessionState.CONNECTED,
                SessionState.CLOSING,
            },
            SessionState.CONNECTED: {
                SessionState.ACTIVE,
                SessionState.CLOSING,
            },
            SessionState.ACTIVE: {
                SessionState.CLOSING,
            },
            SessionState.CLOSING: {
                SessionState.CLOSED,
            },
            SessionState.CLOSED: set(),
        }

        if new_state not in valid_transitions[self.state]:
            raise SessionStateError(
                f"Invalid session state transition: "
                f"{self.state.value} -> {new_state.value}"
            )

        self.state = new_state


class SessionManager:
    """Owns the lifecycle and registry of active runtime sessions."""

    def __init__(self) -> None:
        self._sessions: dict[UUID, Session] = {}

    def create(
        self,
        *,
        transport: TransportType,
        remote_address: tuple[str, int],
        local_address: tuple[str, int] | None = None,
    ) -> Session:
        session = Session(
            transport=transport,
            remote_address=remote_address,
            local_address=local_address,
        )

        if session.id in self._sessions:
            raise RuntimeError(f"Session ID collision: {session.id}")

        self._sessions[session.id] = session
        return session

    def get(self, session_id: UUID) -> Session | None:
        return self._sessions.get(session_id)

    def remove(self, session_id: UUID) -> Session | None:
        return self._sessions.pop(session_id, None)

    def active_count(self) -> int:
        return sum(
            session.state != SessionState.CLOSED
            for session in self._sessions.values()
        )

    def close_all(self) -> None:
        for session in tuple(self._sessions.values()):
            session.close()

    def clear_closed(self) -> None:
        closed_ids = [
            session_id
            for session_id, session in self._sessions.items()
            if session.state == SessionState.CLOSED
        ]

        for session_id in closed_ids:
            del self._sessions[session_id]
