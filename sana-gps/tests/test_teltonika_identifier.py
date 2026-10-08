from __future__ import annotations

import pytest

from app.protocols.teltonika.identifier import (
    TeltonikaIdentificationError,
    TeltonikaIdentifier,
)


VALID_IMEI = "352094082143253"


def _frame(imei: str) -> bytes:
    payload = imei.encode("ascii")
    return len(payload).to_bytes(2, "big") + payload


def test_teltonika_identifier_extracts_imei() -> None:
    result = TeltonikaIdentifier().identify(_frame(VALID_IMEI))

    assert result.imei == VALID_IMEI


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"\x00",
        b"\x00\x0f" + VALID_IMEI.encode("ascii") + b"extra",
        b"\x00\x0e" + VALID_IMEI.encode("ascii"),
        b"\x00\x0f" + b"35209408214325a",
    ],
)
def test_teltonika_identifier_rejects_invalid_frames(data: bytes) -> None:
    with pytest.raises(TeltonikaIdentificationError):
        TeltonikaIdentifier().identify(data)


def test_teltonika_identifier_rejects_non_ascii_identifier() -> None:
    payload = b"35209408214325" + bytes([0xFF])
    data = len(payload).to_bytes(2, "big") + payload

    with pytest.raises(TeltonikaIdentificationError):
        TeltonikaIdentifier().identify(data)


def test_real_fmb920_handshake_frame_is_accepted() -> None:
    data = bytes.fromhex("000f333532303934303832313433323533")

    result = TeltonikaIdentifier().identify(data)

    assert result.imei == VALID_IMEI
