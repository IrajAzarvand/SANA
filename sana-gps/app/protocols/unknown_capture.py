from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UnknownProtocolSample:
    """A bounded raw sample from a connection not matched by known detectors."""

    session_id: UUID
    remote_address: tuple[str, int]
    transport: str
    payload: bytes
    captured_at: datetime


class UnknownProtocolCapture:
    """In-memory, bounded capture queue; deliberately performs no decoding or execution."""

    def __init__(self, *, max_samples: int = 256, max_sample_bytes: int = 8192) -> None:
        if max_samples < 1:
            raise ValueError("max_samples must be positive")
        if max_sample_bytes < 1:
            raise ValueError("max_sample_bytes must be positive")
        self._samples: deque[UnknownProtocolSample] = deque(maxlen=max_samples)
        self._max_sample_bytes = max_sample_bytes
        self._dropped = 0
        self._lock = Lock()

    def record(self, *, session_id: UUID, remote_address: tuple[str, int],
               transport: str, payload: bytes) -> bool:
        """Record one raw chunk. Oversized chunks are dropped rather than truncated."""
        if not payload or len(payload) > self._max_sample_bytes:
            with self._lock:
                self._dropped += 1
            return False
        sample = UnknownProtocolSample(
            session_id=session_id,
            remote_address=remote_address,
            transport=transport,
            payload=bytes(payload),
            captured_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._samples.append(sample)
        return True

    def snapshot(self) -> tuple[UnknownProtocolSample, ...]:
        """Return an immutable snapshot of currently retained samples."""
        with self._lock:
            return tuple(self._samples)

    @property
    def dropped_count(self) -> int:
        with self._lock:
            return self._dropped
