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
        TeltonikaAVLDecoder().decode(_codec8_frame(codec=0x07))


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



def _codec8e_frame() -> bytes:
    timestamp = int(datetime(2026, 10, 10, 12, 4, 57, tzinfo=timezone.utc).timestamp() * 1000)
    record = (
        timestamp.to_bytes(8, "big")
        + b"\x00"
        + int(459321070).to_bytes(4, "big", signed=True)
        + int(378546450).to_bytes(4, "big", signed=True)
        + int(123).to_bytes(2, "big", signed=True)
        + int(180).to_bytes(2, "big")
        + bytes((8,))
        + int(50).to_bytes(2, "big")
        + int(0x0102).to_bytes(2, "big")  # event IO id
        + int(2).to_bytes(2, "big")  # total IO count
        + int(1).to_bytes(2, "big") + int(256).to_bytes(2, "big") + b"\x01"
        + b"\x00\x00"  # 2-byte values
        + b"\x00\x00"  # 4-byte values
        + b"\x00\x00"  # 8-byte values
        + int(1).to_bytes(2, "big")
        + int(512).to_bytes(2, "big")
        + int(3).to_bytes(2, "big")
        + bytes.fromhex("616263")
    )
    data = bytes((0x8E, 1)) + record + b"\x01"
    crc = TeltonikaAVLDecoder._crc16_ibm(data)
    return b"\x00\x00\x00\x00" + len(data).to_bytes(4, "big") + data + crc.to_bytes(4, "big")


def test_codec8_extended_decodes_wide_ids_and_variable_length_io() -> None:
    message = TeltonikaAVLDecoder().decode(_codec8e_frame())
    assert message.codec_id == 0x8E
    record = message.records[0]
    assert record.codec_id == 0x8E
    assert record.event_io_id == 0x0102
    assert record.io_elements == {256: 1, 512: "hex:616263"}



def _codec16_frame() -> bytes:
    timestamp = int(datetime(2026, 10, 10, 12, 4, 57, tzinfo=timezone.utc).timestamp() * 1000)
    record = (
        timestamp.to_bytes(8, "big")
        + b"\x00"
        + int(459321070).to_bytes(4, "big", signed=True)
        + int(378546450).to_bytes(4, "big", signed=True)
        + int(123).to_bytes(2, "big", signed=True)
        + int(180).to_bytes(2, "big")
        + bytes((8,))
        + int(50).to_bytes(2, "big")
        + int(0x0102).to_bytes(2, "big")
        + b"\x01"  # generation type
        + b"\x01"  # total IO count
        + b"\x01" + int(239).to_bytes(2, "big") + b"\x01"
        + b"\x00"
        + b"\x00"
        + b"\x00"
    )
    data = bytes((0x10, 1)) + record + b"\x01"
    crc = TeltonikaAVLDecoder._crc16_ibm(data)
    return b"\x00\x00\x00\x00" + len(data).to_bytes(4, "big") + data + crc.to_bytes(4, "big")


def _teltonika_serial_frame(codec: int, payload: bytes) -> bytes:
    data = bytes((codec, 1)) + payload + b"\x01"
    crc = TeltonikaAVLDecoder._crc16_ibm(data)
    return b"\x00\x00\x00\x00" + len(data).to_bytes(4, "big") + data + crc.to_bytes(4, "big")


def test_codec16_decodes_generation_type_and_wide_io_ids() -> None:
    message = TeltonikaAVLDecoder().decode(_codec16_frame())
    record = message.records[0]
    assert message.codec_id == 0x10
    assert record.generation_type == 1
    assert record.event_io_id == 0x0102
    assert record.io_elements == {239: 1}


@pytest.mark.parametrize(
    ("codec", "record_payload", "expected_text"),
    [
        (0x0C, b"\x05" + (3).to_bytes(4, "big") + b"abc", "abc"),
        (0x0D, b"\x01" + (7).to_bytes(4, "big") + (1_791_635_697).to_bytes(4, "big") + b"abc", "abc"),
    ],
)
def test_teltonika_non_avl_messages_are_interpreted_and_preserved(
    codec: int, record_payload: bytes, expected_text: str
) -> None:
    message = TeltonikaAVLDecoder().decode(_teltonika_serial_frame(codec, record_payload))
    assert message.records == ()
    assert message.message_type == "command_or_text"
    assert message.message_details["records"][0]["payload_text"] == expected_text
