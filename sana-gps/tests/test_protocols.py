from dataclasses import dataclass

import pytest

from app.protocols.registry import ProtocolRegistry
from app.protocols.types import DetectionResult, ProtocolFrame, ProtocolId


@dataclass(frozen=True, slots=True)
class FakeTeltonikaDetector:
    protocol: ProtocolId = ProtocolId.TELTONIKA

    def detect(self, data: bytes) -> DetectionResult:
        return DetectionResult(
            protocol=self.protocol,
            matched=data.startswith(b"TEL")
        )


@dataclass(frozen=True, slots=True)
class FakeGT06Detector:
    protocol: ProtocolId = ProtocolId.GT06

    def detect(self, data: bytes) -> DetectionResult:
        return DetectionResult(
            protocol=self.protocol,
            matched=data.startswith(b"GT06")
        )


@dataclass(frozen=True, slots=True)
class FakeUnknownDetector:
    protocol: ProtocolId = ProtocolId.UNKNOWN

    def detect(self, data: bytes) -> DetectionResult:
        return DetectionResult(protocol=self.protocol, matched=True)


def test_protocol_id_contains_supported_protocols() -> None:
    assert ProtocolId.UNKNOWN.value == "unknown"
    assert ProtocolId.TELTONIKA.value == "teltonika"
    assert ProtocolId.GT06.value == "gt06"


def test_protocol_frame_keeps_protocol_and_raw_bytes() -> None:
    frame = ProtocolFrame(protocol=ProtocolId.TELTONIKA, data=b"raw-frame")

    assert frame.protocol is ProtocolId.TELTONIKA
    assert frame.data == b"raw-frame"


def test_detection_result_unknown_is_explicit() -> None:
    result = DetectionResult.unknown()

    assert result.protocol is ProtocolId.UNKNOWN
    assert result.matched is False


def test_registry_registers_and_returns_detector() -> None:
    detector = FakeTeltonikaDetector()
    registry = ProtocolRegistry()

    registry.register(detector)

    assert registry.get(ProtocolId.TELTONIKA) is detector
    assert registry.protocols() == (ProtocolId.TELTONIKA,)


def test_registry_rejects_duplicate_protocol() -> None:
    registry = ProtocolRegistry([FakeTeltonikaDetector()])

    with pytest.raises(ValueError, match="already registered"):
        registry.register(FakeTeltonikaDetector())


def test_registry_rejects_unknown_detector() -> None:
    registry = ProtocolRegistry()

    with pytest.raises(ValueError, match="UNKNOWN"):
        registry.register(FakeUnknownDetector())


def test_registry_detects_first_matching_protocol() -> None:
    registry = ProtocolRegistry(
        [FakeTeltonikaDetector(), FakeGT06Detector()]
    )

    result = registry.detect(b"GT06-packet")

    assert result.protocol is ProtocolId.GT06
    assert result.matched is True


def test_registry_returns_unknown_when_nothing_matches() -> None:
    registry = ProtocolRegistry(
        [FakeTeltonikaDetector(), FakeGT06Detector()]
    )

    result = registry.detect(b"unknown-packet")

    assert result.protocol is ProtocolId.UNKNOWN
    assert result.matched is False


def test_registry_does_not_depend_on_transport_or_database() -> None:
    registry = ProtocolRegistry([FakeTeltonikaDetector()])

    result = registry.detect(b"TEL-packet")

    assert result == DetectionResult(
        protocol=ProtocolId.TELTONIKA,
        matched=True,
    )
