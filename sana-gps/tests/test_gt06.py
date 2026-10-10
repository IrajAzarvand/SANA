from app.protocols.gt06 import (
    GT06FrameError,
    GT06Framer,
    build_ack,
    crc16_itu,
    decode_position,
    identifier_candidates,
)


def make_frame(protocol: int, information: bytes = b"", serial: int = 1) -> bytes:
    body = bytes([protocol]) + information + serial.to_bytes(2, "big")
    length = len(body) + 2
    length_byte = bytes([length])
    checksum = crc16_itu(length_byte + body).to_bytes(2, "big")
    return b"\x78\x78" + length_byte + body + checksum + b"\x0D\x0A"


def test_gt06_framer_handles_split_packets():
    packet = make_frame(0x13, b"\x00", serial=7)
    framer = GT06Framer()

    assert framer.feed(packet[:4]) == ()
    frames = framer.feed(packet[4:])

    assert len(frames) == 1
    assert frames[0].protocol == 0x13
    assert frames[0].serial == 7
    assert frames[0].raw == packet


def test_gt06_framer_rejects_bad_crc():
    packet = bytearray(make_frame(0x13, b"\x00"))
    packet[-4] ^= 0xFF

    try:
        GT06Framer().feed(bytes(packet))
    except GT06FrameError as exc:
        assert "CRC" in str(exc)
    else:
        raise AssertionError("bad CRC should be rejected")


def test_gt06_login_identifier_candidates_include_ten_digit_id():
    information = bytes.fromhex("0000009176515406")

    assert "9176515406" in identifier_candidates(information)


def test_gt06_ack_contains_protocol_and_serial():
    ack = build_ack(0x13, 0x1234)

    assert ack[:2] == b"\x78\x78"
    assert ack[2] == 5
    assert ack[3] == 0x13
    assert ack[4:6] == b"\x12\x34"
    assert ack[-2:] == b"\x0D\x0A"
    assert int.from_bytes(ack[-4:-2], "big") == crc16_itu(ack[2:-4])


def test_decode_classic_gt06_gps_information():
    info = bytes([26, 10, 10, 12, 30, 45, 8])
    info += int(30 * 1_800_000).to_bytes(4, "big")
    info += int(50 * 1_800_000).to_bytes(4, "big")
    info += bytes([60])
    info += (0x0C00 | 87).to_bytes(2, "big")

    position = decode_position(info)

    assert position.gps_time.year == 2026
    assert position.latitude == 30
    assert position.longitude == 50
    assert position.speed_kmh == 60
    assert position.course == 87
    assert position.satellites == 8
