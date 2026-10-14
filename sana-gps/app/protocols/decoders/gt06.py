from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


class GT06FrameError(ValueError):
    """Raised when a GT06 frame is malformed or has an invalid checksum."""


@dataclass(frozen=True, slots=True)
class GT06Frame:
    protocol: int
    information: bytes
    serial: int
    raw: bytes


@dataclass(frozen=True, slots=True)
class GT06Position:
    gps_time: datetime
    latitude: float
    longitude: float
    speed_kmh: int
    course: int
    satellites: int


def crc16_itu(data: bytes) -> int:
    """GT06 CRC-16/ITU checksum used by common 7878 frames."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return (~crc) & 0xFFFF


def build_ack(protocol: int, serial: int) -> bytes:
    body = bytes((0x05, protocol)) + serial.to_bytes(2, "big")
    checksum = crc16_itu(body).to_bytes(2, "big")
    return b"\x78\x78" + body + checksum + b"\x0D\x0A"


class GT06Framer:
    """Incrementally extracts and validates GT06 TCP frames."""

    def __init__(self, max_buffer_size: int = 8192) -> None:
        self._buffer = bytearray()
        self._max_buffer_size = max_buffer_size

    def feed(self, data: bytes) -> tuple[GT06Frame, ...]:
        self._buffer.extend(data)
        if len(self._buffer) > self._max_buffer_size:
            self._buffer.clear()
            raise GT06FrameError("GT06 TCP buffer limit exceeded")

        frames: list[GT06Frame] = []
        while True:
            start = self._find_header()
            if start < 0:
                # Preserve a possible first byte of a split 7878/7979 header.
                keep = self._buffer[-1:] if self._buffer[-1:] in (b"\x78", b"\x79") else b""
                self._buffer.clear()
                self._buffer.extend(keep)
                break
            if start:
                del self._buffer[:start]

            long_header = self._buffer.startswith(b"\x79\x79")
            header_size = 4 if long_header else 3
            if len(self._buffer) < header_size:
                break
            length_size = 2 if long_header else 1
            length = int.from_bytes(self._buffer[2:2 + length_size], "big")
            if length < 5 or length > self._max_buffer_size:
                del self._buffer[0]
                raise GT06FrameError("Invalid GT06 frame length")

            total = 2 + length_size + length + 2
            if len(self._buffer) < total:
                break
            raw = bytes(self._buffer[:total])
            del self._buffer[:total]

            if raw[-2:] != b"\x0D\x0A":
                raise GT06FrameError("Invalid GT06 frame terminator")
            checksum_offset = total - 4
            expected = int.from_bytes(raw[checksum_offset:checksum_offset + 2], "big")
            actual = crc16_itu(raw[2:checksum_offset])
            if expected != actual:
                raise GT06FrameError("Invalid GT06 CRC")
            protocol_offset = 2 + length_size
            protocol = raw[protocol_offset]
            serial = int.from_bytes(raw[checksum_offset - 2:checksum_offset], "big")
            information = raw[protocol_offset + 1:checksum_offset - 2]
            frames.append(GT06Frame(protocol, information, serial, raw))
        return tuple(frames)

    def _find_header(self) -> int:
        short = self._buffer.find(b"\x78\x78")
        long = self._buffer.find(b"\x79\x79")
        positions = [position for position in (short, long) if position >= 0]
        return min(positions) if positions else -1


def identifier_candidates(information: bytes) -> tuple[str, ...]:
    """Return common BCD/ASCII encodings of the terminal identifier."""
    candidates: list[str] = []
    try:
        digits = "".join(f"{byte >> 4:X}{byte & 0x0F:X}" for byte in information)
        if digits and all(character in "0123456789" for character in digits):
            candidates.extend((digits, digits.lstrip("0")))
    except ValueError:
        pass

    try:
        text = information.decode("ascii").strip("\x00 ")
        if text.isdigit():
            candidates.extend((text, text.lstrip("0")))
    except UnicodeDecodeError:
        pass

    unique = []
    for candidate in candidates:
        if candidate and candidate not in unique:
            unique.append(candidate)
    return tuple(unique)


def decode_position(information: bytes) -> GT06Position:
    """Decode a classic GT06 0x12 GPS information field."""
    if len(information) < 18:
        raise GT06FrameError("GT06 GPS information field is too short")

    year, month, day, hour, minute, second = information[:6]
    try:
        gps_time = datetime(
            2000 + year, month, day, hour, minute, second, tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise GT06FrameError("Invalid GT06 GPS timestamp") from exc

    satellites = information[6] & 0x0F
    latitude_raw = int.from_bytes(information[7:11], "big")
    longitude_raw = int.from_bytes(information[11:15], "big")
    speed_kmh = information[15]
    course_status = int.from_bytes(information[16:18], "big")
    latitude = latitude_raw / 1_800_000
    longitude = longitude_raw / 1_800_000

    # GT06 direction flags: bit 10 latitude north, bit 11 longitude east.
    if not course_status & (1 << 10):
        latitude = -latitude
    if not course_status & (1 << 11):
        longitude = -longitude

    return GT06Position(
        gps_time=gps_time,
        latitude=latitude,
        longitude=longitude,
        speed_kmh=speed_kmh,
        course=course_status & 0x03FF,
        satellites=satellites,
    )
