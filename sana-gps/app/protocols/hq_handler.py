from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID
import logging

from app.protocols.types import ProtocolId, ProtocolResponse
from app.repositories.device import DeviceRepository
from app.repositories.gps_telemetry import GPSTelemetryRepository
from app.transport.session import Session, SessionState

logger = logging.getLogger(__name__)


class HQHandler:
    """Frame and preserve H02/HQ text and binary messages."""

    SHORT_BINARY_LENGTH = 32
    LONG_BINARY_LENGTH = 45

    def __init__(
        self,
        devices: DeviceRepository,
        telemetry: GPSTelemetryRepository,
        *,
        max_buffer_size: int = 8192,
    ) -> None:
        self._devices = devices
        self._telemetry = telemetry
        self._max_buffer_size = max_buffer_size
        self._buffers: dict[UUID, tuple[Session, bytearray]] = {}

    async def handle(self, session: Session, data: bytes) -> ProtocolResponse | None:
        self._cleanup_closed_sessions()
        entry = self._buffers.get(session.id)
        if entry is None:
            buffer = bytearray()
            self._buffers[session.id] = (session, buffer)
        else:
            buffer = entry[1]
        buffer.extend(data)
        if len(buffer) > self._max_buffer_size:
            self._buffers.pop(session.id, None)
            logger.warning("H02 buffer limit exceeded from %s", session.remote_address)
            return None

        while buffer:
            marker = buffer[0]
            if marker == ord("*"):
                end = buffer.find(b"#")
                if end < 0:
                    break
                raw = bytes(buffer[:end + 1])
                del buffer[:end + 1]
                self._process_text_report(session, raw)
                continue

            if marker in (ord("$"), ord("X")):
                frame_length = self._binary_frame_length(buffer, marker)
                if frame_length is None or len(buffer) < frame_length:
                    break
                raw = bytes(buffer[:frame_length])
                del buffer[:frame_length]
                self._process_binary_report(session, raw)
                continue

            # Discard transport noise until the next documented H02 marker.
            next_positions = [
                position for marker_byte in (ord("*"), ord("$"), ord("X"))
                if (position := buffer.find(bytes((marker_byte,)), 1)) >= 0
            ]
            if not next_positions:
                # Keep a single byte in case the next read begins a marker sequence.
                buffer.clear()
                break
            del buffer[:min(next_positions)]

        return None

    def _binary_frame_length(self, buffer: bytearray, marker: int) -> int | None:
        if marker == ord("X"):
            return self.SHORT_BINARY_LENGTH

        # H02 '$' frames have short and long device-ID layouts. Prefer the
        # registered ID match so a split long frame is not mistaken for a short one.
        if len(buffer) >= 9:
            long_identifier = bytes(buffer[1:9]).hex()[:15]
            long_device = self._devices.find_by_imei(long_identifier)
            if long_device is not None:
                return self.LONG_BINARY_LENGTH
        if len(buffer) >= 6:
            short_identifier = bytes(buffer[1:6]).hex()
            short_device = self._devices.find_by_imei(short_identifier)
            if short_device is not None:
                return self.SHORT_BINARY_LENGTH

        if len(buffer) >= self.LONG_BINARY_LENGTH:
            return self.LONG_BINARY_LENGTH
        if len(buffer) >= self.SHORT_BINARY_LENGTH:
            # Unknown devices still get a deterministic raw-frame classification.
            return self.SHORT_BINARY_LENGTH
        return None

    def _process_text_report(self, session: Session, raw: bytes) -> None:
        try:
            text = raw.decode("ascii").strip("\x00\r\n ")
        except UnicodeDecodeError:
            logger.warning("Non-ASCII H02 text frame from %s: %s", session.remote_address, raw.hex())
            return
        if not text.startswith("*") or not text.endswith("#"):
            logger.warning("Malformed H02 text frame from %s: %s", session.remote_address, raw.hex())
            return

        fields = text[:-1].split(",")
        if len(fields) < 2 or not fields[1].strip().isdigit():
            logger.warning("H02 message without a numeric device ID from %s: %s", session.remote_address, raw.hex())
            return

        identifier = fields[1].strip()
        device = self._devices.find_by_imei(identifier)
        if device is None or not self._bind_device(session, device):
            logger.warning("Unregistered or mismatched H02 device %s: %s", identifier, raw.hex())
            return

        received_at = datetime.now(timezone.utc)
        gps_time = received_at
        latitude = longitude = speed = course = None
        gps_valid = False
        parsed: dict[str, object] = {
            "message_format": "text",
            "message_marker": fields[0],
            "device_identifier": identifier,
            "message_type": fields[2] if len(fields) > 2 else None,
            "raw_fields": fields,
        }

        # Common position layout:
        # *HQ,id,version,HHMMSS,A/V,lat,N/S,lon,E/W,speed,course,DDMMYY,status,...
        if (
            len(fields) > 11
            and fields[6].strip().upper() in {"N", "S"}
            and fields[8].strip().upper() in {"E", "W"}
        ):
            parsed.update({
                "version": fields[2],
                "device_time_text": fields[3],
                "validity": fields[4],
                "latitude_text": fields[5],
                "latitude_hemisphere": fields[6],
                "longitude_text": fields[7],
                "longitude_hemisphere": fields[8],
                "speed_text": fields[9],
                "course_text": fields[10],
                "date_text": fields[11],
            })
            try:
                gps_time = datetime.strptime(
                    fields[11].strip() + fields[3].strip(), "%d%m%y%H%M%S"
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                parsed["device_time_parse_error"] = True
            try:
                latitude = self._coordinate(fields[5], fields[6], latitude=True)
                longitude = self._coordinate(fields[7], fields[8], latitude=False)
            except (ValueError, IndexError):
                parsed["coordinate_parse_error"] = True
                latitude = longitude = None
            try:
                speed = float(fields[9])
                if speed < 0:
                    speed = None
            except (ValueError, IndexError):
                parsed["speed_parse_error"] = True
            try:
                course = float(fields[10])
            except (ValueError, IndexError):
                parsed["course_parse_error"] = True

            gps_valid = (
                fields[4].strip().upper() in {"A", "B"}
                and latitude is not None
                and longitude is not None
            )
            if len(fields) > 12 and fields[12]:
                parsed["status_hex"] = fields[12].strip()
                try:
                    parsed["status_value"] = int(fields[12].strip(), 16)
                except ValueError:
                    parsed["status_parse_error"] = True
            for index, name in ((13, "mcc"), (14, "mnc"), (15, "lac"), (16, "cell_id")):
                if len(fields) > index:
                    parsed[name] = fields[index].strip()
            if len(fields) > 17:
                parsed["extra_fields"] = fields[17:]

        self._telemetry.save(
            device_id=device.id,
            protocol=ProtocolId.HQ.value,
            gps_time=gps_time,
            latitude=latitude,
            longitude=longitude,
            speed_kmh=speed,
            heading_deg=int(course) if course is not None and 0 <= course <= 360 else None,
            raw_payload=raw,
            attributes={"h02": parsed},
            gps_valid=gps_valid,
            received_at=received_at,
        )

    def _process_binary_report(self, session: Session, raw: bytes) -> None:
        marker = raw[:1]
        if marker == b"$" and len(raw) == self.LONG_BINARY_LENGTH:
            id_bytes = 8
            identifier = raw[1:9].hex()[:15]
        else:
            id_bytes = 5
            identifier = raw[1:1 + id_bytes].hex()

        device = self._devices.find_by_imei(identifier)
        if device is None or not self._bind_device(session, device):
            logger.warning(
                "Unregistered or mismatched H02 binary device %s: %s",
                identifier,
                raw.hex(),
            )
            return

        received_at = datetime.now(timezone.utc)
        base = 1 + id_bytes
        parsed: dict[str, object] = {
            "message_format": "binary",
            "message_type": "binary_position_report" if marker == b"$" else "binary_extension_report",
            "message_marker": marker.decode("ascii", errors="replace"),
            "device_identifier": identifier,
            "frame_length": len(raw),
            "raw_hex": raw.hex(),
        }
        gps_time = received_at
        latitude = longitude = speed = course = None
        gps_valid = False

        if marker != b"$":
            self._telemetry.save(
                device_id=device.id,
                protocol=ProtocolId.HQ.value,
                gps_time=received_at,
                latitude=None,
                longitude=None,
                speed_kmh=None,
                raw_payload=raw,
                attributes={"h02": parsed},
                gps_valid=False,
                received_at=received_at,
            )
            return

        try:
            time_digits = self._bcd_digits(raw[base:base + 6])
            hour, minute, second = int(time_digits[0:2]), int(time_digits[2:4]), int(time_digits[4:6])
            day, month, year = int(time_digits[6:8]), int(time_digits[8:10]), int(time_digits[10:12])
            gps_time = datetime(2000 + year, month, day, hour, minute, second, tzinfo=timezone.utc)
            latitude_digits = self._bcd_digits(raw[base + 6:base + 10])
            longitude_prefix = self._bcd_digits(raw[base + 11:base + 15])
            final_longitude_digit = raw[base + 15] >> 4
            if final_longitude_digit > 9:
                raise ValueError("Invalid BCD longitude digit")
            longitude_digits = longitude_prefix + str(final_longitude_digit)
            latitude = self._degrees_minutes(latitude_digits[:2], latitude_digits[2:8])
            longitude = self._degrees_minutes(longitude_digits[:3], longitude_digits[3:9])
            # The final longitude BCD nibble shares a byte with the H02 status flags.
            flags = raw[base + 15] & 0x0F
            if not flags & 0x04:
                latitude = -latitude
            if not flags & 0x08:
                longitude = -longitude
            gps_valid = bool(flags & 0x02)
            speed_first = raw[base + 16]
            speed_course_shared = raw[base + 17]
            if (speed_first >> 4) > 9 or (speed_first & 0x0F) > 9 or (speed_course_shared >> 4) > 9:
                raise ValueError("Invalid BCD speed")
            speed_digits = f"{speed_first >> 4}{speed_first & 0x0F}{speed_course_shared >> 4}"
            speed = float(int(speed_digits))
            course = (speed_course_shared & 0x0F) * 100 + int(self._bcd_digits(raw[base + 18:base + 19]))
            parsed.update({
                "device_time": gps_time.isoformat(),
                "latitude_bcd": latitude_digits,
                "longitude_bcd": longitude_digits,
                "gps_flags": flags,
                "battery_raw": raw[base + 10],
                "speed_bcd": speed_digits,
                "course": course,
                "course_raw_hex": raw[base + 17:base + 19].hex(),
                "status_raw_hex": raw[base + 19:base + 23].hex(),
                "gps_valid": gps_valid,
            })
            if len(raw) > base + 23:
                parsed["extension_hex"] = raw[base + 23:].hex()
        except (IndexError, ValueError):
            parsed["decode_error"] = "invalid_or_truncated_bcd_fields"

        self._telemetry.save(
            device_id=device.id,
            protocol=ProtocolId.HQ.value,
            gps_time=gps_time,
            latitude=latitude,
            longitude=longitude,
            speed_kmh=speed,
            heading_deg=int(course) if course is not None and 0 <= course <= 360 else None,
            raw_payload=raw,
            attributes={"h02": parsed},
            gps_valid=gps_valid,
            received_at=received_at,
        )

    def _bind_device(self, session: Session, device) -> bool:
        known_protocol = (device.protocol or "").strip().lower()
        if known_protocol and known_protocol != ProtocolId.HQ.value:
            return False
        if not known_protocol:
            self._devices.set_detected_protocol(device.id, ProtocolId.HQ.value)
        if session.device_id is None:
            session.bind_device(device_id=device.id, imei=device.imei, protocol=ProtocolId.HQ)
        elif session.device_id != device.id or session.protocol is not ProtocolId.HQ:
            return False
        return True

    @staticmethod
    def _bcd_digits(data: bytes) -> str:
        digits = []
        for value in data:
            high, low = value >> 4, value & 0x0F
            if high > 9 or low > 9:
                raise ValueError("Invalid BCD digit")
            digits.extend((str(high), str(low)))
        return "".join(digits)

    @staticmethod
    def _degrees_minutes(degrees_text: str, minutes_text: str) -> float:
        degrees = int(degrees_text)
        minutes = int(minutes_text) / 10000.0
        if not 0 <= minutes < 60:
            raise ValueError("Invalid BCD coordinate minutes")
        return degrees + minutes / 60

    @staticmethod
    def _coordinate(value: str, hemisphere: str, *, latitude: bool) -> float:
        number = float(value)
        degrees = int(number // 100)
        minutes = number - degrees * 100
        if not 0 <= minutes < 60:
            raise ValueError("Invalid coordinate minutes")
        result = degrees + minutes / 60
        hemisphere = hemisphere.upper()
        allowed = {"N", "S"} if latitude else {"E", "W"}
        if hemisphere not in allowed:
            raise ValueError("Invalid coordinate hemisphere")
        if hemisphere in {"S", "W"}:
            result = -result
        return result

    def _cleanup_closed_sessions(self) -> None:
        for session_id, (session, _) in tuple(self._buffers.items()):
            if session.state is SessionState.CLOSED:
                self._buffers.pop(session_id, None)
