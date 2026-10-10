from __future__ import annotations

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
from app.transport.session import Session, SessionState


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
    ) -> None:
        self._device_repository = device_repository
        self._position_repository = position_repository
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

            if frame.protocol == self.GPS:
                try:
                    position = decode_position(frame.information)
                except GT06FrameError:
                    continue
                self._position_repository.save(
                    device_id=session.device_id,
                    position=position,
                    raw_frame=frame.raw,
                )
                outgoing.extend(build_ack(frame.protocol, frame.serial))
            elif frame.protocol in (self.HEARTBEAT, self.ALARM):
                outgoing.extend(build_ack(frame.protocol, frame.serial))

        return ProtocolResponse(bytes(outgoing)) if outgoing else None

    def _cleanup_closed_sessions(self) -> None:
        closed_ids = [
            session_id
            for session_id, (session, _) in self._framers.items()
            if session.state is SessionState.CLOSED
        ]
        for session_id in closed_ids:
            self._framers.pop(session_id, None)
