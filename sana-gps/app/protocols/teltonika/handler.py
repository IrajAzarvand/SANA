from __future__ import annotations

from uuid import UUID

from app.protocols.teltonika.framer import TeltonikaFrameError, TeltonikaFramer
from app.protocols.teltonika.identifier import TeltonikaIdentifier
from app.protocols.types import ProtocolFrame, ProtocolId, ProtocolResponse
from app.repositories.device import DeviceRepository
from app.transport.session import Session, SessionState


class TeltonikaHandler:
    """Coordinates Teltonika framing, identification, and session binding."""

    def __init__(
        self,
        device_repository: DeviceRepository,
        *,
        max_buffer_size: int = 4096,
    ) -> None:
        self._device_repository = device_repository
        self._identifier = TeltonikaIdentifier()
        self._max_buffer_size = max_buffer_size
        self._framers: dict[UUID, tuple[Session, TeltonikaFramer]] = {}

    async def handle(
        self,
        session: Session,
        data: bytes,
    ) -> ProtocolResponse | None:
        self._cleanup_closed_sessions()

        entry = self._framers.get(session.id)
        if entry is None:
            framer = TeltonikaFramer(max_buffer_size=self._max_buffer_size)
            self._framers[session.id] = (session, framer)
        else:
            framer = entry[1]

        try:
            frames = framer.feed(data)
        except TeltonikaFrameError:
            self._forget(session)
            return ProtocolResponse(b"\x00")

        response: ProtocolResponse | None = None

        for frame in frames:
            if session.device_id is None:
                response = self._handle_identification(session, frame)
                if response.data == b"\x00":
                    self._forget(session)
                    return response
                continue

            if frame.protocol is not ProtocolId.TELTONIKA:
                self._forget(session)
                return ProtocolResponse(b"\x00")

            # AVL decoding and the post-commit record-count response belong
            # to the next processing stage. Do not acknowledge telemetry yet.

        return response

    def _handle_identification(
        self,
        session: Session,
        frame: ProtocolFrame,
    ) -> ProtocolResponse:
        try:
            identification = self._identifier.identify(frame.data)
        except ValueError:
            return ProtocolResponse(b"\x00")

        device = self._device_repository.find_by_imei(identification.imei)
        if device is None:
            return ProtocolResponse(b"\x00")

        if device.protocol.strip().lower() != ProtocolId.TELTONIKA.value:
            return ProtocolResponse(b"\x00")

        session.bind_device(
            device_id=device.id,
            imei=device.imei,
            protocol=ProtocolId.TELTONIKA,
        )
        return ProtocolResponse(b"\x01")

    def _forget(self, session: Session) -> None:
        self._framers.pop(session.id, None)

    def _cleanup_closed_sessions(self) -> None:
        closed_ids = [
            session_id
            for session_id, (session, _) in self._framers.items()
            if session.state is SessionState.CLOSED
        ]
        for session_id in closed_ids:
            self._framers.pop(session_id, None)
