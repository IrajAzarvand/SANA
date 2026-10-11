from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from app.protocols.teltonika.decoder import TeltonikaAVLDecoder, TeltonikaDecodeError
from app.protocols.teltonika.framer import TeltonikaFrameError, TeltonikaFramer
from app.protocols.teltonika.identifier import TeltonikaIdentifier
from app.protocols.teltonika.normalizer import TeltonikaNormalizer
from app.protocols.types import ProtocolFrame, ProtocolId, ProtocolResponse
from app.repositories.device import DeviceRepository
from app.repositories.gps_telemetry import GPSTelemetryRepository
from app.transport.session import Session, SessionState

logger = logging.getLogger(__name__)


class TeltonikaHandler:
    """Coordinates Teltonika identification, Codec 8 decoding and persistence."""

    def __init__(
        self,
        device_repository: DeviceRepository,
        telemetry_repository: GPSTelemetryRepository | None = None,
        *,
        max_buffer_size: int = 4096,
    ) -> None:
        self._device_repository = device_repository
        self._telemetry_repository = telemetry_repository
        self._identifier = TeltonikaIdentifier()
        self._decoder = TeltonikaAVLDecoder()
        self._normalizer = TeltonikaNormalizer()
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
        except TeltonikaFrameError as exc:
            logger.warning("Invalid Teltonika frame from %s: %s", session.remote_address, exc)
            self._forget(session)
            return ProtocolResponse(b"\x00")

        outgoing = bytearray()
        for frame in frames:
            if session.device_id is None:
                response = self._handle_identification(session, frame)
                outgoing.extend(response.data)
                if response.data == b"\x00":
                    self._forget(session)
                    return ProtocolResponse(bytes(outgoing))
                continue

            if frame.protocol is not ProtocolId.TELTONIKA:
                self._forget(session)
                return ProtocolResponse(b"\x00")

            try:
                message = self._decoder.decode(frame.data)
            except TeltonikaDecodeError as exc:
                logger.warning(
                    "Rejected Teltonika AVL frame for device %s from %s: %s",
                    session.device_imei,
                    session.remote_address,
                    exc,
                )
                outgoing.extend(b"\x00\x00\x00\x00")
                continue

            if self._telemetry_repository is None:
                logger.error("Teltonika telemetry repository is not configured")
                # No AVL success ACK when persistence is unavailable.
                continue

            received_at = datetime.now(timezone.utc)
            normalized = tuple(
                self._normalizer.normalize(
                    device_id=session.device_id,
                    record=record,
                    server_received_at=received_at,
                )
                for record in message.records
            )
            try:
                accepted_count = self._telemetry_repository.save_batch(
                    normalized,
                    protocol=ProtocolId.TELTONIKA.value,
                    raw_payload=message.raw_frame,
                )
            except Exception:
                logger.exception(
                    "Failed to commit Teltonika AVL batch for device %s",
                    session.device_imei,
                )
                # A DB failure must not be acknowledged as successfully stored.
                continue

            # Teltonika's AVL ACK is the number of records accepted, big-endian.
            outgoing.extend(accepted_count.to_bytes(4, "big"))

        return ProtocolResponse(bytes(outgoing)) if outgoing else None

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

        known_protocol = (device.protocol or "").strip().lower()
        if known_protocol and known_protocol != ProtocolId.TELTONIKA.value:
            return ProtocolResponse(b"\x00")

        if not known_protocol:
            self._device_repository.set_detected_protocol(
                device.id,
                ProtocolId.TELTONIKA.value,
            )

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
