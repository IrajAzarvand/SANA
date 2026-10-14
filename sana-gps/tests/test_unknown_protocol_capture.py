from __future__ import annotations

from app.protocols.unknown_capture import UnknownProtocolCapture
from app.transport.session import Session, TransportType


def make_session() -> Session:
    session = Session(transport=TransportType.TCP, remote_address=("127.0.0.1", 50001))
    session.connect()
    session.activate()
    return session


def test_capture_keeps_only_the_newest_bounded_samples():
    capture = UnknownProtocolCapture(max_samples=2, max_sample_bytes=8)
    session = make_session()

    assert capture.record(session_id=session.id, remote_address=session.remote_address,
                         transport=session.transport.value, payload=b"first")
    assert capture.record(session_id=session.id, remote_address=session.remote_address,
                         transport=session.transport.value, payload=b"second")
    assert capture.record(session_id=session.id, remote_address=session.remote_address,
                         transport=session.transport.value, payload=b"third")

    samples = capture.snapshot()
    assert [sample.payload for sample in samples] == [b"second", b"third"]
    assert all(sample.session_id == session.id for sample in samples)


def test_capture_drops_empty_and_oversized_samples_without_truncating():
    capture = UnknownProtocolCapture(max_samples=2, max_sample_bytes=4)
    session = make_session()

    assert not capture.record(session_id=session.id, remote_address=session.remote_address,
                              transport=session.transport.value, payload=b"")
    assert not capture.record(session_id=session.id, remote_address=session.remote_address,
                              transport=session.transport.value, payload=b"12345")
    assert capture.snapshot() == ()
    assert capture.dropped_count == 2
