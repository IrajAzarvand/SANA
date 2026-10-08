import pytest

from app.protocols.framing import FramingBuffer, FramingBufferOverflowError


def test_buffer_starts_empty() -> None:
    buffer = FramingBuffer(max_size=16)
    assert len(buffer) == 0
    assert buffer.peek() == b""


def test_append_and_peek_do_not_consume_data() -> None:
    buffer = FramingBuffer(max_size=16)
    buffer.append(b"ABC")
    assert len(buffer) == 3
    assert buffer.peek() == b"ABC"
    assert buffer.peek(2) == b"AB"
    assert len(buffer) == 3


def test_append_multiple_chunks_preserves_order() -> None:
    buffer = FramingBuffer(max_size=16)
    buffer.append(b"ABC")
    buffer.append(b"DEF")
    assert buffer.peek() == b"ABCDEF"


def test_consume_removes_exact_number_of_bytes() -> None:
    buffer = FramingBuffer(max_size=16)
    buffer.append(b"ABCDEF")
    assert buffer.consume(2) == b"AB"
    assert buffer.peek() == b"CDEF"
    assert len(buffer) == 4


def test_consume_all_empties_buffer() -> None:
    buffer = FramingBuffer(max_size=16)
    buffer.append(b"ABC")
    assert buffer.consume(3) == b"ABC"
    assert len(buffer) == 0
    assert buffer.peek() == b""


def test_consume_more_than_available_is_rejected() -> None:
    buffer = FramingBuffer(max_size=16)
    buffer.append(b"ABC")
    with pytest.raises(ValueError, match="cannot consume"):
        buffer.consume(4)
    assert buffer.peek() == b"ABC"


def test_empty_append_is_a_no_op() -> None:
    buffer = FramingBuffer(max_size=16)
    buffer.append(b"")
    assert len(buffer) == 0


def test_buffer_rejects_non_positive_max_size() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        FramingBuffer(max_size=0)


def test_buffer_rejects_data_that_exceeds_limit() -> None:
    buffer = FramingBuffer(max_size=5)
    buffer.append(b"1234")
    with pytest.raises(FramingBufferOverflowError, match="limit exceeded"):
        buffer.append(b"56")
    assert buffer.peek() == b"1234"


def test_buffer_rejects_cumulative_overflow() -> None:
    buffer = FramingBuffer(max_size=5)
    buffer.append(b"12")
    buffer.append(b"34")
    with pytest.raises(FramingBufferOverflowError):
        buffer.append(b"56")
    assert buffer.peek() == b"1234"


def test_clear_discards_buffered_data() -> None:
    buffer = FramingBuffer(max_size=16)
    buffer.append(b"ABC")
    buffer.clear()
    assert len(buffer) == 0
    assert buffer.peek() == b""


def test_consume_zero_does_not_change_buffer() -> None:
    buffer = FramingBuffer(max_size=16)
    buffer.append(b"ABC")
    assert buffer.consume(0) == b""
    assert buffer.peek() == b"ABC"


def test_negative_sizes_are_rejected() -> None:
    buffer = FramingBuffer(max_size=16)
    with pytest.raises(ValueError, match="must not be negative"):
        buffer.peek(-1)
    with pytest.raises(ValueError, match="must not be negative"):
        buffer.consume(-1)
