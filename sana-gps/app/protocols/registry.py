from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from app.protocols.types import DetectionResult, ProtocolId


class ProtocolDetector(Protocol):
    """Minimal contract for a protocol detector."""

    @property
    def protocol(self) -> ProtocolId:
        ...

    def detect(self, data: bytes) -> DetectionResult:
        ...


class ProtocolRegistry:
    """Registry of protocol detectors used by the detection layer."""

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
