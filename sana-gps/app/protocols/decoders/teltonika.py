from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


class TeltonikaDecodeError(ValueError):
    """Raised when a Teltonika AVL frame is malformed or unsupported."""


@dataclass(frozen=True, slots=True)
class TeltonikaAVLRecord:
    device_time: datetime
    priority: int
    longitude: float
    latitude: float
    altitude_m: int
    heading_deg: int
    satellites: int
    speed_kmh: int
    event_io_id: int
    io_elements: dict[int, int]


@dataclass(frozen=True, slots=True)
class TeltonikaProtocolMessage:
    codec_id: int
    records: tuple[TeltonikaAVLRecord, ...]
    raw_frame: bytes


class TeltonikaAVLDecoder:
    """Decode Teltonika Codec 8 AVL frames; transport/framing stays separate."""

    CODEC_8 = 0x08
    PREAMBLE = b"\x00\x00\x00\x00"
    MAX_RECORDS = 255

    def decode(self, frame: bytes) -> TeltonikaProtocolMessage:
        if len(frame) < 15:
            raise TeltonikaDecodeError("AVL frame is too short")
        if frame[:4] != self.PREAMBLE:
            raise TeltonikaDecodeError("Invalid AVL preamble")

        data_length = int.from_bytes(frame[4:8], "big")
        if data_length < 3 or data_length > 1280 or len(frame) != 12 + data_length:
            raise TeltonikaDecodeError("AVL frame length does not match its header or limit")

        data = frame[8:8 + data_length]
        received_crc = int.from_bytes(frame[-4:], "big")
        calculated_crc = self._crc16_ibm(data)
        if received_crc != calculated_crc:
            raise TeltonikaDecodeError("Invalid Teltonika AVL CRC")

        codec_id = data[0]
        if codec_id != self.CODEC_8:
            raise TeltonikaDecodeError(
                f"Unsupported Teltonika codec 0x{codec_id:02x}; Codec 8 is required for MVP"
            )

        declared_count = data[1]
        if declared_count == 0 or declared_count > self.MAX_RECORDS:
            raise TeltonikaDecodeError("Invalid AVL record count")

        cursor = 2
        records: list[TeltonikaAVLRecord] = []
        for _ in range(declared_count):
            record, cursor = self._decode_record(data, cursor)
            records.append(record)

        if cursor >= len(data):
            raise TeltonikaDecodeError("Missing trailing AVL record count")
        trailing_count = data[cursor]
        cursor += 1
        if trailing_count != declared_count:
            raise TeltonikaDecodeError("AVL record counts do not match")
        if cursor != len(data):
            raise TeltonikaDecodeError("Unexpected bytes after AVL records")

        return TeltonikaProtocolMessage(
            codec_id=codec_id,
            records=tuple(records),
            raw_frame=frame,
        )

    def _decode_record(
        self, data: bytes, cursor: int
    ) -> tuple[TeltonikaAVLRecord, int]:
        # Timestamp (8), priority (1), GPS element (15).
        self._require(data, cursor, 24)
        timestamp_ms = int.from_bytes(data[cursor:cursor + 8], "big")
        cursor += 8
        priority = data[cursor]
        cursor += 1

        longitude_raw = int.from_bytes(data[cursor:cursor + 4], "big", signed=True)
        latitude_raw = int.from_bytes(data[cursor + 4:cursor + 8], "big", signed=True)
        altitude_m = int.from_bytes(data[cursor + 8:cursor + 10], "big", signed=True)
        heading_deg = int.from_bytes(data[cursor + 10:cursor + 12], "big")
        satellites = data[cursor + 12]
        speed_kmh = int.from_bytes(data[cursor + 13:cursor + 15], "big")
        cursor += 15

        # Codec 8 IO: event id, total count, then 1/2/4/8-byte value groups.
        self._require(data, cursor, 2)
        event_io_id = data[cursor]
        total_io = data[cursor + 1]
        cursor += 2
        io_elements: dict[int, int] = {}

        for value_size in (1, 2, 4, 8):
            self._require(data, cursor, 1)
            count = data[cursor]
            cursor += 1
            self._require(data, cursor, count * (1 + value_size))
            for _ in range(count):
                io_id = data[cursor]
                value = int.from_bytes(data[cursor + 1:cursor + 1 + value_size], "big")
                cursor += 1 + value_size
                if io_id in io_elements:
                    raise TeltonikaDecodeError(f"Duplicate AVL IO id {io_id}")
                io_elements[io_id] = value

        if len(io_elements) != total_io:
            raise TeltonikaDecodeError("AVL IO element count does not match")
        try:
            device_time = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as exc:
            raise TeltonikaDecodeError("Invalid AVL timestamp") from exc

        return (
            TeltonikaAVLRecord(
                device_time=device_time,
                priority=priority,
                longitude=longitude_raw / 10_000_000,
                latitude=latitude_raw / 10_000_000,
                altitude_m=altitude_m,
                heading_deg=heading_deg,
                satellites=satellites,
                speed_kmh=speed_kmh,
                event_io_id=event_io_id,
                io_elements=io_elements,
            ),
            cursor,
        )

    @staticmethod
    def _require(data: bytes, cursor: int, amount: int) -> None:
        if amount < 0 or cursor < 0 or cursor + amount > len(data):
            raise TeltonikaDecodeError("Truncated Teltonika AVL record")

    @staticmethod
    def _crc16_ibm(data: bytes) -> int:
        crc = 0
        for byte in data:
            crc ^= byte
            for _ in range(8):
                crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
        return crc
