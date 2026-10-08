from __future__ import annotations

from enum import Enum

from app.protocols.framing import FramingBuffer
from app.protocols.types import ProtocolFrame, ProtocolId


class TeltonikaFrameError(ValueError):
    """Raised when a Teltonika frame cannot be interpreted."""


class TeltonikaFrameType(str, Enum):
    IDENTIFICATION = "identification"
    AVL = "avl"


class TeltonikaFramer:
    """Incrementally extracts Teltonika identification and AVL frames from TCP bytes."""

    AVL_PREAMBLE = b"\x00\x00\x00\x00"
    AVL_HEADER_SIZE = 8
    AVL_TRAILER_SIZE = 4
    MAX_AVL_DATA_LENGTH = 1280

    def __init__(self, *, max_buffer_size: int = 4096) -> None:
        self._buffer = FramingBuffer(max_buffer_size)
        self._awaiting_identification = True

    @property
    def awaiting_identification(self) -> bool:
        return self._awaiting_identification

    def feed(self, data: bytes) -> tuple[ProtocolFrame, ...]:
        self._buffer.append(data)
        frames: list[ProtocolFrame] = []

        while True:
            if self._awaiting_identification:
                frame = self._extract_identification()
                if frame is None:
                    break
                frames.append(frame)
                self._awaiting_identification = False
                continue

            frame = self._extract_avl()
            if frame is None:
                break
            frames.append(frame)

        return tuple(frames)

    def _extract_identification(self) -> ProtocolFrame | None:
        if len(self._buffer) < 2:
            return None

        declared_length = int.from_bytes(self._buffer.peek(2), "big")
        total_length = 2 + declared_length

        if total_length > self._buffer.max_size:
            raise TeltonikaFrameError(
                "Teltonika identification frame exceeds the buffer limit"
            )

        if len(self._buffer) < total_length:
            return None

        data = self._buffer.consume(total_length)
        return ProtocolFrame(protocol=ProtocolId.TELTONIKA, data=data)

    def _extract_avl(self) -> ProtocolFrame | None:
        if len(self._buffer) < self.AVL_HEADER_SIZE:
            return None

        header = self._buffer.peek(self.AVL_HEADER_SIZE)
        if header[:4] != self.AVL_PREAMBLE:
            raise TeltonikaFrameError("Invalid Teltonika AVL preamble")

        data_length = int.from_bytes(header[4:8], "big")

        if data_length < 3:
            raise TeltonikaFrameError("Teltonika AVL data field is too short")

        if data_length > self.MAX_AVL_DATA_LENGTH:
            raise TeltonikaFrameError(
                "Teltonika AVL data field exceeds the protocol limit"
            )

        total_length = 4 + 4 + data_length + self.AVL_TRAILER_SIZE
        if total_length > self._buffer.max_size:
            raise TeltonikaFrameError(
                "Teltonika AVL frame exceeds the buffer limit"
            )

        if len(self._buffer) < total_length:
            return None

        data = self._buffer.consume(total_length)
        return ProtocolFrame(protocol=ProtocolId.TELTONIKA, data=data)
