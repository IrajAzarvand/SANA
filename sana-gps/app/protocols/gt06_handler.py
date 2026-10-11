from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.protocols.gt06 import (
    GT06FrameError,
    GT06Framer,
    build_ack,
    decode_position,
    identifier_candidates,
)
from app.protocols.types import ProtocolId, ProtocolResponse
from app.repositories.device import DeviceRepository
from app.repositories.gt06_position import GT06PositionRepository
from app.repositories.gps_telemetry import GPSTelemetryRepository
from app.transport.session import Session, SessionState


class GT06Handler:
    """Decode common GT06 reports and persist every identified packet, including unknown types."""

    LOGIN = 0x01
    GPS_TYPES = {0x10, 0x12}
    HEARTBEAT = 0x13
    ALARM = 0x16

    MESSAGE_NAMES = {
        0x01: "login",
        0x10: "gps",
        0x11: "gps_lbs_variant_1",
        0x12: "gps_lbs",
        0x13: "heartbeat_status",
        0x14: "satellite_or_gps_status",
        0x15: "string_information",
        0x16: "gps_lbs_alarm",
        0x17: "wifi_or_rfid",
        0x18: "lbs_extended",
        0x19: "lbs_status",
        0x1A: "gps_phone",
        0x1E: "gps_lbs_extended",
        0x21: "string_information",
        0x22: "gps_lbs_variant_2",
        0x23: "heartbeat_variant",
        0x24: "multiple_lbs",
        0x25: "gps_lbs_driver",
        0x26: "gps_lbs_status",
        0x27: "gps_lbs_status_variant",
        0x28: "multiple_lbs_variant",
        0x2C: "lbs_wifi",
        0x2D: "gps_lbs_variant_3",
        0x2E: "multiple_lbs_variant_2",
        0x37: "gps_lbs_variant_4",
        0x38: "gps_lbs_variant_5",
        0x40: "battery_management",
        0x41: "multimedia",
        0x61: "ibutton",
        0x65: "diagnostic_trouble_codes",
        0x66: "obd_pid",
        0x80: "server_command",
        0x81: "server_command_response",
        0x82: "server_command_response_variant",
        0x8A: "time_request",
        0x8C: "obd_data",
        0x94: "device_information",
        0x95: "alarm_report",
        0x97: "address_response",
        0x9B: "serial_data",
        0xA0: "gps_lbs_variant_6",
        0xA1: "lbs_variant",
        0xA2: "wifi_or_status_variant",
        0xA3: "fence_or_status",
        0xA4: "multi_fence",
        0xA5: "lbs_alarm",
        0xA7: "lbs_address",
        0xF2: "peripheral_data",
        0xF3: "wifi_variant",
    }

    # These packet types are commonly sent by terminals and use the standard GT06 ACK.
    ACK_TYPES = {
        0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A,
        0x1E, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2C, 0x2D,
        0x2E, 0x37, 0x38, 0x40, 0x41, 0x61, 0x65, 0x66, 0x8A, 0x8C, 0x94,
        0x95, 0x9B, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0xA7, 0xF2, 0xF3,
    }

    def __init__(
        self,
        device_repository: DeviceRepository,
        position_repository: GT06PositionRepository,
        telemetry_repository: GPSTelemetryRepository | None = None,
        *,
        max_buffer_size: int = 8192,
    ) -> None:
        self._device_repository = device_repository
        self._position_repository = position_repository
        self._telemetry_repository = telemetry_repository
        self._max_buffer_size = max_buffer_size
        self._framers: dict[UUID, tuple[Session, GT06Framer]] = {}

    async def handle(self, session: Session, data: bytes) -> ProtocolResponse | None:
        self._cleanup_closed_sessions()
        entry = self._framers.get(session.id)
        if entry is None:
            framer = GT06Framer(self._max_buffer_size)
            self._framers[session.id] = (session, framer)
        else:
            framer = entry[1]

        try:
            frames = framer.feed(data)
        except GT06FrameError:
            self._framers.pop(session.id, None)
            return None

        outgoing = bytearray()
        for frame in frames:
            if frame.protocol == self.LOGIN:
                if session.device_id is not None:
                    continue
                device = None
                for identifier in identifier_candidates(frame.information):
                    device = self._device_repository.find_by_imei(identifier)
                    if device is not None:
                        break
                if device is None:
                    continue

                known_protocol = (device.protocol or "").strip().lower()
                if known_protocol and known_protocol != ProtocolId.GT06.value:
                    continue
                if not known_protocol:
                    self._device_repository.set_detected_protocol(
                        device.id, ProtocolId.GT06.value
                    )
                session.bind_device(
                    device_id=device.id,
                    imei=device.imei,
                    protocol=ProtocolId.GT06,
                )
                outgoing.extend(build_ack(frame.protocol, frame.serial))
                continue

            if session.device_id is None or session.protocol is not ProtocolId.GT06:
                continue

            self._persist_message(session, frame)
            if frame.protocol in self.ACK_TYPES:
                outgoing.extend(build_ack(frame.protocol, frame.serial))

        return ProtocolResponse(bytes(outgoing)) if outgoing else None

    def _persist_message(self, session: Session, frame) -> None:
        received_at = datetime.now(timezone.utc)
        name = self.MESSAGE_NAMES.get(frame.protocol, "unknown")
        attributes: dict[str, object] = {
            "gt06": {
                "message_type": frame.protocol,
                "message_name": name,
                "serial": frame.serial,
                "information_length": len(frame.information),
                "information_hex": frame.information.hex(),
                "raw_frame_hex": frame.raw.hex(),
                "recognized_type": frame.protocol in self.MESSAGE_NAMES,
            }
        }
        position = None

        # The classic GT06 GPS element starts with YY MM DD hh mm ss, then
        # satellite/coordinate/speed/course fields. Other variants are retained
        # as raw events until their model-specific layout is established.
        if frame.protocol in self.GPS_TYPES:
            try:
                position = decode_position(frame.information)
            except GT06FrameError:
                attributes["gt06"]["position_decode_error"] = True
            else:
                attributes["gt06"]["position"] = {
                    "latitude": position.latitude,
                    "longitude": position.longitude,
                    "speed_kmh": position.speed_kmh,
                    "course": position.course,
                    "satellites": position.satellites,
                    "gps_time": position.gps_time.isoformat(),
                }
                self._position_repository.save(
                    device_id=session.device_id,
                    position=position,
                    raw_frame=frame.raw,
                )

        if self._telemetry_repository is not None:
            self._telemetry_repository.save(
                device_id=session.device_id,
                protocol=ProtocolId.GT06.value,
                gps_time=position.gps_time if position else received_at,
                latitude=position.latitude if position else None,
                longitude=position.longitude if position else None,
                speed_kmh=position.speed_kmh if position else None,
                heading_deg=position.course if position else None,
                satellites=position.satellites if position else None,
                raw_payload=frame.raw,
                attributes=attributes,
                gps_valid=position is not None,
                received_at=received_at,
            )

    def _cleanup_closed_sessions(self) -> None:
        closed_ids = [
            session_id
            for session_id, (session, _) in self._framers.items()
            if session.state is SessionState.CLOSED
        ]
        for session_id in closed_ids:
            self._framers.pop(session_id, None)
