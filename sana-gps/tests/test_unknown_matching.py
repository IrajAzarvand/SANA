from __future__ import annotations

from app.protocols.unknown_capture import UnknownProtocolCapture
from app.protocols.unknown_matching import match_registered_identifiers
from app.transport.session import Session, TransportType


def make_session() -> Session:
    session = Session(transport=TransportType.TCP, remote_address=("127.0.0.1", 50002))
    session.connect()
    session.activate()
    return session


def test_capture_reassembles_chunks_per_session_within_limit():
    capture = UnknownProtocolCapture(max_stream_bytes=32)
    session = make_session()
    assert capture.record(session_id=session.id, remote_address=session.remote_address,
                          transport="tcp", payload=b"*HQ,9176")
    assert capture.record(session_id=session.id, remote_address=session.remote_address,
                          transport="tcp", payload=b"515720,V1#")
    streams = capture.stream_snapshot()
    assert len(streams) == 1
    assert streams[0].payload == b"*HQ,9176515720,V1#"
    assert streams[0].truncated is False


def test_capture_marks_stream_truncated_instead_of_claiming_complete():
    capture = UnknownProtocolCapture(max_stream_bytes=5)
    session = make_session()
    capture.record(session_id=session.id, remote_address=session.remote_address,
                   transport="tcp", payload=b"1234")
    capture.record(session_id=session.id, remote_address=session.remote_address,
                   transport="tcp", payload=b"5678")
    stream = capture.stream_snapshot()[0]
    assert stream.payload == b"1234"
    assert stream.truncated is True


def test_matcher_finds_complete_ascii_identifier_and_avoids_partial_digit_match():
    identifiers = ("9176515720", "352094082143253", "9176515720")
    assert match_registered_identifiers(b"*HQ,9176515720,V1#", identifiers) == ("9176515720",)
    assert match_registered_identifiers(b"X191765157201Y", ("9176515720",)) == ()
    assert match_registered_identifiers(bytes.fromhex("9176515720"), ("9176515720",)) == ()


def test_matcher_finds_packed_bcd_identifier():
    identifier = "19176533355"
    leading_zero_bcd = bytes.fromhex("019176533355")
    trailing_f_bcd = bytes.fromhex("19176533355f")
    delimiter = bytes([126])
    assert match_registered_identifiers(delimiter + leading_zero_bcd + delimiter,
                                        (identifier,)) == (identifier,)
    assert match_registered_identifiers(delimiter + trailing_f_bcd + delimiter,
                                        (identifier,)) == (identifier,)


def test_matcher_finds_binary_integer_identifier_in_both_byte_orders():
    identifier = "19176533355"
    value = int(identifier)
    width = (value.bit_length() + 7) // 8
    big_endian = value.to_bytes(width, "big")
    little_endian = value.to_bytes(width, "little")
    delimiter = bytes([126])
    assert match_registered_identifiers(delimiter + big_endian + delimiter,
                                        (identifier,)) == (identifier,)
    assert match_registered_identifiers(delimiter + little_endian + delimiter,
                                        (identifier,)) == (identifier,)


def test_matcher_does_not_guess_for_empty_payload():
    assert match_registered_identifiers(b"", ("19176533355",)) == ()
