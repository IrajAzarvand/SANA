from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.protocols.types import ProtocolId, ProtocolResponse
from app.repositories.device import DeviceRepository
from app.repositories.gps_telemetry import GPSTelemetryRepository
from app.transport.session import Session, SessionState


class HQHandler:
    """Frame and preserve H02/HQ messages, including reports without a GPS fix."""

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
            return None

        # H02 text packets are '#' terminated. Keep incomplete TCP reads intact.
        while b"#" in buffer:
            end = buffer.index(b"#") + 1
            raw = bytes(buffer[:end])
            del buffer[:end]
            self._process_text_report(session, raw)
        return None

    def _process_text_report(self, session: Session, raw: bytes) -> None:
        try:
            text = raw.decode("ascii").strip("\x00\r\n ")
        except UnicodeDecodeError:
            self._save_unidentified(session, raw, "non_ascii_text_frame")
            return
        if not text.startswith("*") or not text.endswith("#"):
            self._save_unidentified(session, raw, "unknown_text_frame")
            return

        fields = text[:-1].split(",")
        if len(fields) < 2 or not fields[1].strip().isdigit():
            self._save_unidentified(session, raw, "missing_device_identifier", fields=fields)
            return

        # H02 uses several message types (V1, LINK, SMS, NBR, ...), not just
        # position reports. Preserve all fields even when no position is present.
        identifier = fields[1].strip()
        device = self._devices.find_by_imei(identifier)
        if device is None:
            self._save_unidentified(
                session, raw, "unregistered_device", fields=fields, identifier=identifier
            )
            return
        if not self._bind_device(session, device):
            return

        received_at = datetime.now(timezone.utc)
        gps_time = received_at
        latitude = longitude = speed = course = None
        gps_valid = False
        parsed: dict[str, object] = {
            "message_marker": fields[0],
            "device_identifier": identifier,
            "message_type": fields[2] if len(fields) > 2 else None,
            "raw_fields": fields,
        }

        # The common V1/Vx position format is:
        # *HQ,id,version,HHMMSS,A/V,lat,N/S,lon,E/W,speed,course,DDMMYY,status,...
        if len(fields) > 11:
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
            # Common H02 cellular fields. Retain their original text because
            # devices vary in field count and not all firmware uses the same layout.
            for index, name in ((13, "mcc"), (14, "mnc"), (15, "lac"), (16, "cell_id")):
                if len(fields) > index:
                    parsed[name] = fields[index].strip()

        extras_start = 17 if len(fields) > 17 else 12
        if len(fields) > extras_start:
            parsed["extra_fields"] = fields[extras_start:]

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
            session.bind_device(
                device_id=device.id, imei=device.imei, protocol=ProtocolId.HQ
            )
        elif session.device_id != device.id or session.protocol is not ProtocolId.HQ:
            return False
        return True

    def _save_unidentified(
        self,
        session: Session,
        raw: bytes,
        reason: str,
        *,
        fields: list[str] | None = None,
        identifier: str | None = None,
    ) -> None:
        # The session may not be linked to a registered device yet, so there is no
        # safe device_id for the telemetry table. Keep a structured warning in logs.
        import logging
        logging.getLogger(__name__).warning(
            "Unassociated H02 frame from %s (%s): %s",
            session.remote_address,
            reason,
            raw.hex(),
        )

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
