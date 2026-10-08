from __future__ import annotations

from app.protocols.teltonika.framer import TeltonikaFramer
from app.protocols.types import ProtocolId

IMEI_FRAME = bytes.fromhex("000f333532303934303832313433323533")


def _avl_frame(data_field: bytes) -> bytes:
    return b"\x00\x00\x00\x00" + len(data_field).to_bytes(4, "big") + data_field + b"\x12\x34\x56\x78"


def test_framer_extracts_identification_frame() -> None:
    framer = TeltonikaFramer()
    frames = framer.feed(IMEI_FRAME)
    assert len(frames) == 1
    assert frames[0].protocol is ProtocolId.TELTONIKA
    assert frames[0].data == IMEI_FRAME
    assert not framer.awaiting_identification


def test_framer_waits_for_split_identification_frame() -> None:
    framer = TeltonikaFramer()
    assert framer.feed(IMEI_FRAME[:7]) == ()
    assert framer.feed(IMEI_FRAME[7:]) == ()


def test_framer_extracts_avl_after_identification() -> None:
    framer = TeltonikaFramer()
    framer.feed(IMEI_FRAME)
    avl = _avl_frame(b"\x08\x01\x00")
    frames = framer.feed(avl)
    assert len(frames) == 1
    assert frames[0].data == avl


def test_framer_handles_split_avl_frame() -> None:
    framer = TeltonikaFramer()
    framer.feed(IMEI_FRAME)
    avl = _avl_frame(b"\x08\x01\x00\x00\x01")
    split = len(avl) // 2
    assert framer.feed(avl[:split]) == ()
    assert framer.feed(avl[split:]) == ()


def test_framer_handles_multiple_avl_frames_in_one_tcp_read() -> None:
    framer = TeltonikaFramer()
    framer.feed(IMEI_FRAME)
    first = _avl_frame(b"\x08\x01\x00")
    second = _avl_frame(b"\x08\x01\x00\x01")
    frames = framer.feed(first + second)
    assert [frame.data for frame in frames] == [first, second]


def test_framer_handles_identification_and_avl_in_one_read() -> None:
    framer = TeltonikaFramer()
    avl = _avl_frame(b"\x08\x01\x00")
    frames = framer.feed(IMEI_FRAME + avl)
    assert [frame.data for frame in frames] == [IMEI_FRAME, avl]
