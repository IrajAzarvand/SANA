from __future__ import annotations


class FramingBufferOverflowError(BufferError):
    """Raised when appending data would exceed the framing buffer limit."""


class FramingBuffer:
    """Bounded byte buffer for protocol-specific framers."""

    def __init__(self, max_size: int) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be greater than zero")
        self._max_size = max_size
        self._buffer = bytearray()

    @property
    def max_size(self) -> int:
        return self._max_size

    def __len__(self) -> int:
        return len(self._buffer)

    def append(self, data: bytes) -> None:
        if not data:
            return
        new_size = len(self._buffer) + len(data)
        if new_size > self._max_size:
            raise FramingBufferOverflowError(
                f"framing buffer limit exceeded: {new_size} > {self._max_size}"
            )
        self._buffer.extend(data)

    def peek(self, size: int | None = None) -> bytes:
        if size is None:
            return bytes(self._buffer)
        if size < 0:
            raise ValueError("size must not be negative")
        return bytes(self._buffer[:size])

    def consume(self, size: int) -> bytes:
        if size < 0:
            raise ValueError("size must not be negative")
        if size > len(self._buffer):
            raise ValueError(
                f"cannot consume {size} bytes from a {len(self._buffer)}-byte buffer"
            )
        data = bytes(self._buffer[:size])
        del self._buffer[:size]
        return data

    def clear(self) -> None:
        self._buffer.clear()
