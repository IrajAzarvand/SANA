from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProtocolId(str, Enum):
    """Identifiers for wire protocols supported by SANA GPS."""

    UNKNOWN = "unknown"
    TELTONIKA = "teltonika"
    GT06 = "gt06"
    HQ = "hq*"


@dataclass(frozen=True, slots=True)
class ProtocolFrame:
    """A complete protocol frame produced by a framer."""

    protocol: ProtocolId
    data: bytes


@dataclass(frozen=True, slots=True)
class ProtocolResponse:
    """Generic bytes to send back to a GPS device."""

    data: bytes


@dataclass(frozen=True, slots=True)
class DetectionResult:
    """The outcome of protocol detection for a candidate payload."""

    protocol: ProtocolId
    matched: bool

    @classmethod
    def unknown(cls) -> "DetectionResult":
        return cls(protocol=ProtocolId.UNKNOWN, matched=False)
