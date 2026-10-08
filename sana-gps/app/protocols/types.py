from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProtocolId(str, Enum):
    """Identifiers for wire protocols supported by SANA GPS."""

    UNKNOWN = "unknown"
    TELTONIKA = "teltonika"
    GT06 = "gt06"


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


class TeltonikaIdentificationError(ValueError):
    """Raised when a Teltonika identification frame is invalid."""


@dataclass(frozen=True, slots=True)
class TeltonikaIdentification:
    """The device identity extracted from a Teltonika TCP handshake."""

    imei: str


class TeltonikaIdentifier:
    """Parses the Teltonika two-byte-length-prefixed device identifier."""

    IDENTIFIER_LENGTH = 15

    def identify(self, data: bytes) -> TeltonikaIdentification:
        if len(data) < 2:
            raise TeltonikaIdentificationError("Teltonika identification frame is too short")
        declared_length = int.from_bytes(data[:2], byteorder="big")
        if declared_length != len(data) - 2:
            raise TeltonikaIdentificationError("Teltonika identification length does not match payload")
        payload = data[2:]
        if len(payload) != self.IDENTIFIER_LENGTH:
            raise TeltonikaIdentificationError("Teltonika device identifier must contain exactly 15 bytes")
        return TeltonikaIdentification(imei=payload.decode("ascii"))
