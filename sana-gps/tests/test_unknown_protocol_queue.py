from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

from app.repositories.unknown_protocol_queue import UnknownProtocolQueueRepository


class FakeCursor:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, chunks=(), insert_row=(1,)):
        self.chunks = list(chunks)
        self.insert_row = insert_row
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "INSERT INTO public.fleet_unknowngpsdata" in sql:
            return FakeCursor([self.insert_row] if self.insert_row is not None else [])
        if "SELECT session_id" in sql:
            return FakeCursor([(SESSION_ID,)])
        if "SELECT raw_payload" in sql:
            return FakeCursor([(chunk,) for chunk in self.chunks])
        return FakeCursor()


class FakePool:
    def __init__(self, connection):
        self.fake_connection = connection

    @contextmanager
    def connection(self):
        yield self.fake_connection


SESSION_ID = uuid4()


def test_record_chunk_persists_raw_bytes_and_applies_storage_limits():
    connection = FakeConnection()
    repository = UnknownProtocolQueueRepository(FakePool(connection))

    assert repository.record_chunk(
        session_id=SESSION_ID,
        transport="tcp",
        remote_address=("192.0.2.10", 50123),
        payload=b"raw-packet",
    )

    sql, params = connection.calls[0]
    assert "INSERT INTO public.fleet_unknowngpsdata" in sql
    assert params[3] == b"raw-packet"
    assert "100000" not in sql  # The bound is passed as a query parameter.


def test_pending_session_is_matched_after_chunks_are_reassembled():
    connection = FakeConnection(chunks=(b"*HQ,9176", b"515720,V1#"))
    repository = UnknownProtocolQueueRepository(FakePool(connection))

    matched = repository.match_pending_sessions(("9176515720",))

    assert matched == 1
    update_calls = [call for call in connection.calls if "UPDATE public.fleet_unknowngpsdata" in call[0]]
    assert len(update_calls) == 1
    assert update_calls[0][1] == ("9176515720", SESSION_ID)


def test_ambiguous_identifier_matches_are_left_pending():
    connection = FakeConnection(chunks=(b"*GPS,9176515720,352094082143253#",))
    repository = UnknownProtocolQueueRepository(FakePool(connection))

    matched = repository.match_pending_sessions(("9176515720", "352094082143253"))

    assert matched == 0
    assert not any("UPDATE public.fleet_unknowngpsdata" in sql for sql, _ in connection.calls)


def test_record_chunk_returns_false_when_database_rejects_capacity():
    connection = FakeConnection(insert_row=None)
    repository = UnknownProtocolQueueRepository(FakePool(connection))

    assert not repository.record_chunk(
        session_id=SESSION_ID,
        transport="tcp",
        remote_address=("192.0.2.10", 50123),
        payload=b"raw-packet",
    )
