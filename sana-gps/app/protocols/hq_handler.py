from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from app.protocols.h02_binary import H02BinaryError, decode_h02_binary
from app.protocols.types import ProtocolId, ProtocolResponse
from app.repositories.device import DeviceRepository
from app.repositories.gps_telemetry import GPSTelemetryRepository
from app.transport.session import Session, SessionManager, SessionState


logger = logging.getLogger(__name__)


class HQHandler:
    """Parser for H02 text reports and the observed 45-byte binary reports."""

    BINARY_FRAME_LENGTH = 45

    def __init__(
        self,
        devices: DeviceRepository,
        telemetry: GPSTelemetryRepository,
        *,
        max_buffer_size: int = 8192,
        session_manager: SessionManager | None = None,
    ) -> None:
        self._devices = devices
        self._telemetry = telemetry
        self._max_buffer_size = max_buffer_size
        self._session_manager = session_manager
        self._buffers: dict[UUID, tuple[Session, bytearray]] = {}

    async def handle(self, session: Session, data: bytes) -> ProtocolResponse | None:
        self._cleanup_closed_sessions()
        if not self._is_current_session(session):
            return None
        entry = self._buffers.get(session.id)
        if entry is None:
            buffer = bytearray()
            self._buffers[session.id] = (session, buffer)
        else:
            buffer = entry[1]
        buffer.extend(data)
        if len(buffer) > self._max_buffer_size:
            logger.warning("Dropping oversized H02 buffer from %s", session.remote_address)
            self._buffers.pop(session.id, None)
            return None

        # TCP reads are not message boundaries. Text reports end with '#';
        # the observed binary H02 variant is a fixed 45-byte report.
        while buffer:
            if buffer[0] == 0x24:  # '$' binary marker
                if len(buffer) < self.BINARY_FRAME_LENGTH:
                    break
                raw = bytes(buffer[:self.BINARY_FRAME_LENGTH])
                del buffer[:self.BINARY_FRAME_LENGTH]
                self._process_binary_report(session, raw)
                continue

            if buffer[0] not in (ord("*"), ord("X")):
                # Discard noise up to the next recognizable H02 marker.
                starts = [p for p in (buffer.find(b"$"), buffer.find(b"*"), buffer.find(b"X")) if p >= 0]
                if not starts:
                    buffer.clear()
                    break
                del buffer[:min(starts)]
                continue

            end = buffer.find(b"#")
            if end < 0:
                break
            raw = bytes(buffer[:end + 1])
            del buffer[:end + 1]
            self._process_report(session, raw)
        return None

    def _bind_device(self, session: Session, device) -> bool:
        known_protocol = (device.protocol or "").strip().lower()
        if known_protocol and known_protocol != ProtocolId.HQ.value:
            return False
        if session.device_id is None:
            if self._session_manager is None:
                session.bind_device(device_id=device.id, imei=device.imei, protocol=ProtocolId.HQ)
            else:
                self._session_manager.bind_device(
                    session, device_id=device.id, imei=device.imei, protocol=ProtocolId.HQ
                )
            return True
        return session.device_id == device.id and session.protocol is ProtocolId.HQ

    def _process_binary_report(self, session: Session, raw: bytes) -> None:
        try:
            report = decode_h02_binary(raw)
        except H02BinaryError as exc:
            logger.warning("Invalid H02 binary report from %s: %s; raw=%s",
                           session.remote_address, exc, raw.hex())
            return

        logger.info(
            "Decoded H02 binary report: imei=%s time=%s lat=%.6f lon=%.6f "
            "speed_kmh=%s valid=%s battery=%s",
            report.imei, report.gps_time.isoformat(), report.latitude,
            report.longitude, report.speed_kmh, report.valid, report.battery_level,
        )

        # Match the complete decoded identifier only. Never silently truncate
        # a 15-digit IMEI to match an unrelated/shorter database identifier.
        device = self._devices.find_by_imei(report.imei)
        if device is None:
            logger.warning("Unregistered H02 binary device %s", report.imei)
            return
        if not self._bind_device(session, device):
            logger.warning("H02 binary protocol/device mismatch for %s", report.imei)
            return

        # The canonical telemetry adapter currently derives GPS validity from
        # coordinate presence, so don't persist reports whose protocol flag
        # explicitly marks the fix invalid.
        if not report.valid:
            logger.info("H02 binary report has no valid GPS fix: imei=%s", report.imei)
            return

        if not self._is_current_session(session):
            return
        from app.policies.device_access import device_access_denial_reason
        denial_reason = device_access_denial_reason(device)
        if denial_reason is not None:
            logger.warning("Rejected ineligible HQ telemetry %s: %s", device.imei, denial_reason)
            return
        self._telemetry.save(
            device_id=device.id,
            protocol=ProtocolId.HQ.value,
            gps_time=report.gps_time,
            latitude=report.latitude,
            longitude=report.longitude,
            speed_kmh=report.speed_kmh,
            raw_payload=raw,
        )
        logger.info(
            "Saved H02 binary telemetry: imei=%s device_id=%s time=%s lat=%.6f lon=%.6f",
            report.imei, device.id, report.gps_time.isoformat(), report.latitude, report.longitude,
        )

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

        identifier = fields[1].strip()
        if not identifier or not identifier.isdigit():
            return
        device = self._devices.find_by_imei(identifier)
        if device is None or not self._bind_device(session, device):
            return

        try:
            latitude = self._coordinate(fields[5], fields[6], latitude=True)
            longitude = self._coordinate(fields[7], fields[8], latitude=False)
            speed = float(fields[9])
            gps_time = datetime.strptime(fields[11] + fields[3], "%d%m%y%H%M%S").replace(tzinfo=timezone.utc)
        except (ValueError, IndexError):
            return
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180 and speed >= 0):
            return
        if not self._is_current_session(session):
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
        logger.info(
            "Saved HQ telemetry: imei=%s device_id=%s time=%s lat=%.6f lon=%.6f speed_kmh=%.2f",
            identifier, device.id, gps_time.isoformat(), latitude, longitude, speed,
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

    def _is_current_session(self, session: Session) -> bool:
        if self._session_manager is None or session.device_id is None:
            return True
        return self._session_manager.is_current(session)

    def _cleanup_closed_sessions(self) -> None:
        for session_id, (session, _) in tuple(self._buffers.items()):
            if session.state is SessionState.CLOSED:
                self._buffers.pop(session_id, None)
