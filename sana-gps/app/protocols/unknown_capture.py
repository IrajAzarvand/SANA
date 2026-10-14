from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UnknownProtocolSample:
    """A bounded raw chunk from a connection not matched by known detectors."""

    session_id: UUID
    remote_address: tuple[str, int]
    transport: str
    payload: bytes
    captured_at: datetime


@dataclass(frozen=True, slots=True)
class UnknownProtocolStream:
    """Bounded concatenation of chunks received on one unknown-protocol session."""

    session_id: UUID
    remote_address: tuple[str, int]
    transport: str
    payload: bytes
    first_seen_at: datetime
    last_seen_at: datetime
    truncated: bool


@dataclass(slots=True)
class _StreamState:
    remote_address: tuple[str, int]
    transport: str
    payload: bytearray
    first_seen_at: datetime
    last_seen_at: datetime
    truncated: bool = False


class UnknownProtocolCapture:
    """Bounded in-memory raw capture; deliberately performs no decoding or execution."""

    def __init__(
        self,
        *,
        max_samples: int = 256,
        max_sample_bytes: int = 8192,
        max_sessions: int = 128,
        max_stream_bytes: int = 8192,
    ) -> None:
        if max_samples < 1:
            raise ValueError("max_samples must be positive")
        if max_sample_bytes < 1:
            raise ValueError("max_sample_bytes must be positive")
        if max_sessions < 1:
            raise ValueError("max_sessions must be positive")
        if max_stream_bytes < 1:
            raise ValueError("max_stream_bytes must be positive")
        self._samples: deque[UnknownProtocolSample] = deque(maxlen=max_samples)
        self._streams: dict[UUID, _StreamState] = {}
        self._max_sample_bytes = max_sample_bytes
        self._max_sessions = max_sessions
        self._max_stream_bytes = max_stream_bytes
        self._dropped = 0
        self._lock = Lock()

    def record(
        self,
        *,
        session_id: UUID,
        remote_address: tuple[str, int],
        transport: str,
        payload: bytes,
    ) -> bool:
        """Record a raw chunk and append it to that session's bounded byte stream."""
        if not payload or len(payload) > self._max_sample_bytes:
            with self._lock:
                self._dropped += 1
            return False

        now = datetime.now(timezone.utc)
        sample = UnknownProtocolSample(
            session_id=session_id,
            remote_address=remote_address,
            transport=transport,
            payload=bytes(payload),
            captured_at=now,
        )
        with self._lock:
            self._samples.append(sample)
            state = self._streams.get(session_id)
            if state is None:
                if len(self._streams) >= self._max_sessions:
                    # Evict the least recently updated stream to keep memory bounded.
                    oldest_id = min(self._streams, key=lambda key: self._streams[key].last_seen_at)
                    del self._streams[oldest_id]
                    self._dropped += 1
                state = _StreamState(
                    remote_address=remote_address,
                    transport=transport,
                    payload=bytearray(),
                    first_seen_at=now,
                    last_seen_at=now,
                )
                self._streams[session_id] = state
            state.last_seen_at = now
            if not state.truncated:
                remaining = self._max_stream_bytes - len(state.payload)
                if len(payload) <= remaining:
                    state.payload.extend(payload)
                else:
                    # Never silently truncate and then pretend the stream is complete.
                    state.truncated = True
                    self._dropped += 1
        return True

    def snapshot(self) -> tuple[UnknownProtocolSample, ...]:
        """Return an immutable snapshot of retained raw chunks."""
        with self._lock:
            return tuple(self._samples)

    def stream_snapshot(self) -> tuple[UnknownProtocolStream, ...]:
        """Return bounded per-session streams for identifier matching and analysis."""
        with self._lock:
            return tuple(
                UnknownProtocolStream(
                    session_id=session_id,
                    remote_address=state.remote_address,
                    transport=state.transport,
                    payload=bytes(state.payload),
                    first_seen_at=state.first_seen_at,
                    last_seen_at=state.last_seen_at,
                    truncated=state.truncated,
                )
                for session_id, state in self._streams.items()
            )

    @property
    def dropped_count(self) -> int:
        with self._lock:
            return self._dropped
