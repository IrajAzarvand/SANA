from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.protocols.types import ProtocolId, ProtocolResponse
from app.repositories.device import DeviceRepository
from app.repositories.gps_telemetry import GPSTelemetryRepository
from app.transport.session import Session, SessionState


class HQHandler:
    """Parser for the observed *HQ,...# text GPS report format."""

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

        # The observed text protocol terminates a report with '#'. TCP read
        # boundaries are not message boundaries, so retain incomplete reports.
        while b"#" in buffer:
            end = buffer.index(b"#") + 1
            raw = bytes(buffer[:end])
            del buffer[:end]
            self._process_report(session, raw)
        return None

    def _process_report(self, session: Session, raw: bytes) -> None:
        try:
            text = raw.decode("ascii").strip("\x00\r\n ")
        except UnicodeDecodeError:
            return
        if not text.startswith("*HQ,") or not text.endswith("#"):
            return
        fields = text[:-1].split(",")
        if len(fields) < 12 or fields[0] != "*HQ":
            return

        # Device ID is a complete field, not an arbitrary substring match.
        identifier = fields[1].strip()
        if not identifier or not identifier.isdigit():
            return
        device = self._devices.find_by_imei(identifier)
        if device is None:
            return
        known_protocol = (device.protocol or "").strip().lower()
        if known_protocol and known_protocol != ProtocolId.HQ.value:
            return
        if not known_protocol:
            self._devices.set_detected_protocol(device.id, ProtocolId.HQ.value)

        if session.device_id is None:
            session.bind_device(device_id=device.id, imei=device.imei, protocol=ProtocolId.HQ)
        elif session.device_id != device.id or session.protocol is not ProtocolId.HQ:
            return

        try:
            # This observed format uses DDMM.MMMM / DDDMM.MMMM coordinates.
            latitude = self._coordinate(fields[5], fields[6], latitude=True)
            longitude = self._coordinate(fields[7], fields[8], latitude=False)
            speed = float(fields[9])
            gps_time = datetime.strptime(fields[11] + fields[3], "%d%m%y%H%M%S").replace(tzinfo=timezone.utc)
        except (ValueError, IndexError):
            return
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180 and speed >= 0):
            return
        self._telemetry.save(
            device_id=device.id,
            protocol=ProtocolId.HQ.value,
            gps_time=gps_time,
            latitude=latitude,
            longitude=longitude,
            speed_kmh=speed,
            raw_payload=raw,
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
