from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.protocols.teltonika.decoder import TeltonikaAVLDecoder, TeltonikaDecodeError
from app.protocols.teltonika.normalizer import TeltonikaNormalizer


def _codec8_frame(*, satellites: int = 8, codec: int = 8) -> bytes:
    timestamp = int(datetime(2026, 10, 10, 12, 4, 57, tzinfo=timezone.utc).timestamp() * 1000)
    record = (
        timestamp.to_bytes(8, "big")
        + b"\x00"
        + int(459321070).to_bytes(4, "big", signed=True)
        + int(378546450).to_bytes(4, "big", signed=True)
        + int(123).to_bytes(2, "big", signed=True)
        + int(180).to_bytes(2, "big")
        + bytes((satellites,))
        + int(50).to_bytes(2, "big")
        + bytes((0, 1, 1, 239, 1, 0, 0, 0))
    )
    data = bytes((codec, 1)) + record + b"\x01"
    crc = TeltonikaAVLDecoder._crc16_ibm(data)
    return b"\x00\x00\x00\x00" + len(data).to_bytes(4, "big") + data + crc.to_bytes(4, "big")


def test_codec8_decoder_extracts_position_and_io() -> None:
    message = TeltonikaAVLDecoder().decode(_codec8_frame())
    assert message.codec_id == 8
    assert len(message.records) == 1
    record = message.records[0]
    assert record.device_time == datetime(2026, 10, 10, 12, 4, 57, tzinfo=timezone.utc)
    assert record.latitude == pytest.approx(37.854645)
    assert record.longitude == pytest.approx(45.932107)
    assert record.altitude_m == 123
    assert record.heading_deg == 180
    assert record.satellites == 8
    assert record.speed_kmh == 50
    assert record.io_elements == {239: 1}


def test_codec8_decoder_rejects_bad_crc() -> None:
    frame = bytearray(_codec8_frame())
    frame[-1] ^= 0x01
    with pytest.raises(TeltonikaDecodeError, match="CRC"):
        TeltonikaAVLDecoder().decode(bytes(frame))


def test_codec8_decoder_rejects_unsupported_codec() -> None:
    with pytest.raises(TeltonikaDecodeError, match="Unsupported"):
        TeltonikaAVLDecoder().decode(_codec8_frame(codec=0x8E))


def test_normalizer_uses_nullable_position_for_no_fix() -> None:
    record = TeltonikaAVLDecoder().decode(_codec8_frame(satellites=0)).records[0]
    normalized = TeltonikaNormalizer().normalize(
        device_id=12,
        record=record,
        server_received_at=datetime(2026, 10, 10, 12, 5, tzinfo=timezone.utc),
    )
    assert normalized.gps_valid is False
    assert normalized.latitude is None
    assert normalized.longitude is None
    assert normalized.speed_kmh is not None
    assert normalized.attributes["teltonika"]["io"] == {"239": 1}
