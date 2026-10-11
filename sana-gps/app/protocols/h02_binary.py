from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


class H02BinaryError(ValueError):
    """Raised when an H02 binary position packet is malformed."""


@dataclass(frozen=True, slots=True)
class H02BinaryPosition:
    imei: str
    gps_time: datetime
    latitude: float
    longitude: float
    speed_kmh: int
    valid: bool
    battery_level: int | None
    status: int
    raw: bytes


def _nibble(value: int) -> int:
    if value > 9:
        raise H02BinaryError("invalid BCD digit")
    return value


def _read_bcd(data: bytes, offset: int, digits: int) -> tuple[int, int]:
    """Read BCD digits like Traccar's BcdUtil; odd digits leave the last byte unconsumed."""
    value = 0
    whole_bytes = digits // 2
    for index in range(whole_bytes):
        byte = data[offset + index]
        value = value * 100 + _nibble(byte >> 4) * 10 + _nibble(byte & 0x0F)
    offset += whole_bytes
    if digits % 2:
        value = value * 10 + _nibble(data[offset] >> 4)
    return value, offset


def _read_time(data: bytes, offset: int) -> tuple[datetime, int]:
    values = []
    for _ in range(6):
        value, offset = _read_bcd(data, offset, 2)
        values.append(value)
    hour, minute, second, day, month, year = values
    try:
        return datetime(2000 + year, month, day, hour, minute, second, tzinfo=timezone.utc), offset
    except ValueError as exc:
        raise H02BinaryError("invalid H02 timestamp") from exc


def _decode_layout(raw: bytes, id_bytes: int) -> H02BinaryPosition:
    # Binary H02 packets use a '$' marker, followed by a BCD-encoded ID.
    if raw[0] != 0x24:
        raise H02BinaryError("invalid H02 marker")
    offset = 1
    imei = raw[offset:offset + id_bytes].hex().upper()
    imei = imei[:15]
    offset += id_bytes
    if not imei or not imei.isdigit():
        raise H02BinaryError("invalid H02 identifier")

    gps_time, offset = _read_time(raw, offset)

    # Latitude: DD + DDDDDD/10000 minutes, matching the reference decoder.
    degrees, offset = _read_bcd(raw, offset, 2)
    minutes_raw, offset = _read_bcd(raw, offset, 6)
    latitude = degrees + (minutes_raw / 10000.0) / 60.0

    battery_raw = raw[offset]
    offset += 1
    if battery_raw == 0:
        battery = None
    elif battery_raw <= 3:
        battery = (battery_raw - 1) * 10
    elif battery_raw <= 6:
        battery = (battery_raw - 1) * 20
    elif battery_raw <= 100:
        battery = battery_raw
    elif 0xF1 <= battery_raw <= 0xF6:
        battery = battery_raw - 0xF0
    else:
        battery = None

    # Longitude is encoded across a nibble boundary in the H02 format.
    lon_degrees, offset = _read_bcd(raw, offset, 2)
    next_byte = raw[offset]
    lon_degrees = lon_degrees * 10 + (next_byte >> 4)
    lon_minutes_first = next_byte & 0x0F
    _nibble(lon_minutes_first)
    offset += 1
    lon_minutes_rest, offset = _read_bcd(raw, offset, 5)
    longitude = ((lon_minutes_first * 10 + lon_minutes_rest / 10000.0) / 60.0) + lon_degrees

    flags = raw[offset] & 0x0F
    offset += 1
    valid = bool(flags & 0x02)
    if not flags & 0x04:
        latitude = -latitude
    if not flags & 0x08:
        longitude = -longitude

    speed, offset = _read_bcd(raw, offset, 3)
    course_prefix = raw[offset] & 0x0F
    offset += 1
    course_tail, offset = _read_bcd(raw, offset, 2)
    _ = course_prefix * 100 + course_tail  # parsed for structural validation
    status = int.from_bytes(raw[offset:offset + 4], "big")

    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise H02BinaryError("decoded H02 coordinates are out of range")

    return H02BinaryPosition(
        imei=imei,
        gps_time=gps_time,
        latitude=latitude,
        longitude=longitude,
        speed_kmh=speed,
        valid=valid,
        battery_level=battery,
        status=status,
        raw=raw,
    )


def decode_h02_binary(raw: bytes) -> H02BinaryPosition:
    """Decode a complete 45-byte H02 binary report.

    Identifier layout is selected by validating the timestamp at each supported
    offset. This accommodates devices that send a 10-digit BCD ID in the newer
    45-byte report as well as the 15-digit ID layout documented by Traccar.
    """
    if len(raw) != 45:
        raise H02BinaryError(f"expected 45-byte H02 report, got {len(raw)}")
    errors = []
    # The known field sample uses a five-byte/10-digit ID. Try it first, then
    # the eight-byte/15-digit variant; an invalid date rejects the wrong layout.
    for id_bytes in (5, 8):
        try:
            return _decode_layout(raw, id_bytes)
        except (H02BinaryError, IndexError) as exc:
            errors.append(str(exc))
    raise H02BinaryError("no valid H02 binary layout: " + "; ".join(errors))
