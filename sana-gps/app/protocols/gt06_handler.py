from __future__ import annotations

import logging
from uuid import UUID

from app.protocols.decoders.gt06 import (
    GT06FrameError,
    GT06Framer,
    build_ack,
    decode_position,
    identifier_candidates,
)
from app.protocols.types import ProtocolId, ProtocolResponse
from app.repositories.device import DeviceRepository
from app.repositories.gt06_position import GT06PositionRepository
from app.protocols.registration import confirm_detected_protocol
from app.transport.session import Session, SessionManager, SessionState


logger = logging.getLogger(__name__)


class GT06Handler:
    """Handles GT06 login, heartbeat acknowledgements, and GPS position reports."""

    LOGIN = 0x01
    GPS = 0x12
    HEARTBEAT = 0x13
    ALARM = 0x16

    def __init__(
        self,
        device_repository: DeviceRepository,
        position_repository: GT06PositionRepository,
        *,
        max_buffer_size: int = 8192,
        session_manager: SessionManager | None = None,
    ) -> None:
        self._device_repository = device_repository
        self._position_repository = position_repository
        self._max_buffer_size = max_buffer_size
        self._session_manager = session_manager
        self._framers: dict[UUID, tuple[Session, GT06Framer]] = {}

    async def handle(self, session: Session, data: bytes) -> ProtocolResponse | None:
        self._cleanup_closed_sessions()
        if not self._is_current_session(session):
            return None
        entry = self._framers.get(session.id)
        if entry is None:
            framer = GT06Framer(self._max_buffer_size)
            self._framers[session.id] = (session, framer)
        else:
            framer = entry[1]

        try:
            frames = framer.feed(data)
        except GT06FrameError as exc:
            logger.warning("Invalid GT06 frame from %s: %s", session.remote_address, exc)
            self._framers.pop(session.id, None)
            return None

        outgoing = bytearray()
        for frame in frames:
            if not self._is_current_session(session):
                break

            if frame.protocol == self.LOGIN:
                if session.device_id is not None:
                    continue
                device = None
                for identifier in identifier_candidates(frame.information):
                    device = self._device_repository.find_by_imei(identifier)
                    if device is not None:
                        break
                if device is None:
                    logger.warning("Unregistered GT06 login from %s", session.remote_address)
                    continue

                if not confirm_detected_protocol(
                    self._device_repository, device, ProtocolId.GT06.value
                ):
                    logger.warning(
                        "GT06 protocol/device mismatch: imei=%s configured_protocol=%s",
                        device.imei, device.protocol,
                    )
                    continue
                if self._session_manager is None:
                    session.bind_device(
                        device_id=device.id,
                        imei=device.imei,
                        protocol=ProtocolId.GT06,
                    )
                else:
                    self._session_manager.bind_device(
                        session,
                        device_id=device.id,
                        imei=device.imei,
                        protocol=ProtocolId.GT06,
                    )
                logger.info(
                    "Registered GT06 session: imei=%s device_id=%s remote=%s",
                    device.imei, device.id, session.remote_address,
                )
                outgoing.extend(build_ack(frame.protocol, frame.serial))
                continue

            if session.device_id is None or session.protocol is not ProtocolId.GT06:
                continue

            if frame.protocol == self.GPS:
                try:
                    position = decode_position(frame.information)
                except GT06FrameError:
                    continue
                if not self._is_current_session(session):
                    continue
                from app.policies.device_access import device_access_denial_reason
                device = self._device_repository.find_by_imei(session.device_imei or "")
                if device is None:
                    logger.warning("GT06 device disappeared before persistence: %s", session.device_imei)
                    continue
                denial_reason = device_access_denial_reason(device)
                if denial_reason is not None:
                    logger.warning("Rejected ineligible GT06 telemetry %s: %s", device.imei, denial_reason)
                    continue
                self._position_repository.save(
                    device_id=session.device_id,
                    position=position,
                    raw_frame=frame.raw,
                )
                logger.info(
                    "Saved GT06 position: imei=%s device_id=%s time=%s lat=%.6f lon=%.6f",
                    session.device_imei, session.device_id, position.gps_time.isoformat(),
                    position.latitude, position.longitude,
                )
                outgoing.extend(build_ack(frame.protocol, frame.serial))
            elif frame.protocol in (self.HEARTBEAT, self.ALARM):
                if self._is_current_session(session):
                    outgoing.extend(build_ack(frame.protocol, frame.serial))

        return ProtocolResponse(bytes(outgoing)) if outgoing else None

    def _is_current_session(self, session: Session) -> bool:
        if self._session_manager is None or session.device_id is None:
            return True
        return self._session_manager.is_current(session)

    def _cleanup_closed_sessions(self) -> None:
        closed_ids = [
            session_id
            for session_id, (session, _) in self._framers.items()
            if session.state is SessionState.CLOSED
        ]
        for session_id in closed_ids:
            self._framers.pop(session_id, None)
