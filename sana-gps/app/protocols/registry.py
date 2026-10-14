from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from app.protocols.types import DetectionResult, ProtocolId


class ProtocolDetector(Protocol):
    """Minimal, transport-independent contract for protocol detection."""

    @property
    def protocol(self) -> ProtocolId:
        ...

    def detect(self, data: bytes) -> DetectionResult:
        ...


@dataclass(frozen=True, slots=True)
class SignatureDetector:
    """Detect a protocol from one of its known wire signatures."""

    protocol: ProtocolId
    prefixes: tuple[bytes, ...]

    def __post_init__(self) -> None:
        if self.protocol is ProtocolId.UNKNOWN:
            raise ValueError("UNKNOWN cannot be registered as a protocol detector")
        if not self.prefixes or any(not prefix for prefix in self.prefixes):
            raise ValueError("A detector requires non-empty protocol signatures")

    def detect(self, data: bytes) -> DetectionResult:
        matched = any(data.startswith(prefix) for prefix in self.prefixes)
        return DetectionResult(protocol=self.protocol, matched=matched)


class ProtocolRegistry:
    """Registry used by the shared TCP dispatcher to detect incoming protocols."""

    def __init__(self, detectors: Iterable[ProtocolDetector] = ()) -> None:
        self._detectors: dict[ProtocolId, ProtocolDetector] = {}
        for detector in detectors:
            self.register(detector)

    def register(self, detector: ProtocolDetector) -> None:
        protocol = detector.protocol
        if protocol is ProtocolId.UNKNOWN:
            raise ValueError("UNKNOWN cannot be registered as a protocol detector")
        if protocol in self._detectors:
            raise ValueError(f"Protocol detector already registered: {protocol.value}")
        self._detectors[protocol] = detector

    def get(self, protocol: ProtocolId) -> ProtocolDetector | None:
        return self._detectors.get(protocol)

    def protocols(self) -> tuple[ProtocolId, ...]:
        return tuple(self._detectors)

    def detect(self, data: bytes) -> DetectionResult:
        for detector in self._detectors.values():
            result = detector.detect(data)
            if result.matched:
                return result
        return DetectionResult.unknown()

    def may_match_prefix(self, data: bytes) -> bool:
        """Return whether data could become a registered signature when more bytes arrive."""
        for detector in self._detectors.values():
            prefixes = getattr(detector, "prefixes", ())
            if any(prefix.startswith(data) for prefix in prefixes):
                return True
        return False


def default_protocol_registry() -> ProtocolRegistry:
    """Build the registry for the protocols currently supported on the shared TCP port."""
    return ProtocolRegistry(
        (
            SignatureDetector(ProtocolId.GT06, (b"\\x78\\x78", b"\\x79\\x79")),
            SignatureDetector(ProtocolId.TELTONIKA, (b"\\x00\\x0f",)),
            SignatureDetector(ProtocolId.HQ, (b"*H", b"$", b"X")),
        )
    )
