from __future__ import annotations

from dataclasses import dataclass


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
            raise TeltonikaIdentificationError(
                "Teltonika identification frame is too short"
            )

        declared_length = int.from_bytes(data[:2], byteorder="big")
        if declared_length != len(data) - 2:
            raise TeltonikaIdentificationError(
                "Teltonika identification length does not match payload"
            )

        payload = data[2:]

        if len(payload) != self.IDENTIFIER_LENGTH:
            raise TeltonikaIdentificationError(
                "Teltonika device identifier must contain exactly 15 bytes"
            )

        if not payload.isascii() or not payload.isdigit():
            raise TeltonikaIdentificationError(
                "Teltonika device identifier must contain only ASCII digits"
            )

        return TeltonikaIdentification(imei=payload.decode("ascii"))
