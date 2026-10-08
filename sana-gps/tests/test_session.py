from datetime import timezone
from time import sleep
from uuid import UUID

import pytest

from app.transport.session import (
    SessionManager,
    SessionState,
    SessionStateError,
    TransportType,
)


def test_session_starts_in_new_state():
    manager = SessionManager()

    session = manager.create(
        transport=TransportType.TCP,
        remote_address=("127.0.0.1", 5000),
        local_address=("127.0.0.1", 9000),
    )

    assert session.state == SessionState.NEW
    assert isinstance(session.id, UUID)
    assert session.transport == TransportType.TCP
    assert session.remote_address == ("127.0.0.1", 5000)
    assert session.local_address == ("127.0.0.1", 9000)
    assert session.created_at.tzinfo == timezone.utc
    assert session.last_activity_at.tzinfo == timezone.utc


def test_session_state_transitions():
    manager = SessionManager()

    session = manager.create(
        transport=TransportType.TCP,
        remote_address=("127.0.0.1", 5000),
    )

    session.connect()
    assert session.state == SessionState.CONNECTED

    session.activate()
    assert session.state == SessionState.ACTIVE

    session.close()
    assert session.state == SessionState.CLOSED


def test_invalid_state_transition_is_rejected():
    manager = SessionManager()

    session = manager.create(
        transport=TransportType.TCP,
        remote_address=("127.0.0.1", 5000),
    )

    with pytest.raises(SessionStateError):
        session.activate()


def test_closed_session_cannot_become_active():
    manager = SessionManager()

    session = manager.create(
        transport=TransportType.TCP,
        remote_address=("127.0.0.1", 5000),
    )

    session.close()

    with pytest.raises(SessionStateError):
        session.activate()


def test_activity_updates_last_activity():
    manager = SessionManager()

    session = manager.create(
        transport=TransportType.TCP,
        remote_address=("127.0.0.1", 5000),
    )

    session.connect()
    session.activate()

    previous_activity = session.last_activity_at

    sleep(0.001)
    session.activity()

    assert session.last_activity_at > previous_activity


def test_activity_requires_active_session():
    manager = SessionManager()

    session = manager.create(
        transport=TransportType.TCP,
        remote_address=("127.0.0.1", 5000),
    )

    with pytest.raises(SessionStateError):
        session.activity()


def test_session_manager_get_and_remove():
    manager = SessionManager()

    session = manager.create(
        transport=TransportType.TCP,
        remote_address=("127.0.0.1", 5000),
    )

    assert manager.get(session.id) is session
    assert manager.active_count() == 1

    removed = manager.remove(session.id)

    assert removed is session
    assert manager.get(session.id) is None
    assert manager.active_count() == 0


def test_session_manager_close_all():
    manager = SessionManager()

    first = manager.create(
        transport=TransportType.TCP,
        remote_address=("127.0.0.1", 5000),
    )
    second = manager.create(
        transport=TransportType.UDP,
        remote_address=("127.0.0.1", 5001),
    )

    first.connect()
    first.activate()

    second.connect()
    second.activate()

    assert manager.active_count() == 2

    manager.close_all()

    assert first.state == SessionState.CLOSED
    assert second.state == SessionState.CLOSED
    assert manager.active_count() == 0


def test_clear_closed_removes_closed_sessions():
    manager = SessionManager()

    session = manager.create(
        transport=TransportType.TCP,
        remote_address=("127.0.0.1", 5000),
    )

    session.close()

    assert manager.get(session.id) is session

    manager.clear_closed()

    assert manager.get(session.id) is None


def test_tcp_and_udp_sessions_have_unique_ids():
    manager = SessionManager()

    tcp_session = manager.create(
        transport=TransportType.TCP,
        remote_address=("127.0.0.1", 5000),
    )

    udp_session = manager.create(
        transport=TransportType.UDP,
        remote_address=("127.0.0.1", 5001),
    )

    assert tcp_session.id != udp_session.id
