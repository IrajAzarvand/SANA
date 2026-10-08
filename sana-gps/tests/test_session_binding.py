from __future__ import annotations

from app.protocols.types import ProtocolId
from app.transport.session import Session, SessionState, TransportType


def make_session() -> Session:
    session = Session(
        transport=TransportType.TCP,
        remote_address=("127.0.0.1", 12345),
    )
    session.connect()
    session.activate()
    return session


def test_session_can_bind_registered_device() -> None:
    session = make_session()

    session.bind_device(
        device_id=42,
        imei="352094082143253",
        protocol=ProtocolId.TELTONIKA,
    )

    assert session.device_id == 42
    assert session.device_imei == "352094082143253"
    assert session.protocol is ProtocolId.TELTONIKA
    assert session.authenticated_at is not None


def test_session_cannot_be_bound_twice() -> None:
    session = make_session()
    session.bind_device(
        device_id=42,
        imei="352094082143253",
        protocol=ProtocolId.TELTONIKA,
    )

    try:
        session.bind_device(
            device_id=43,
            imei="000000000000000",
            protocol=ProtocolId.TELTONIKA,
        )
    except RuntimeError as exc:
        assert "already bound" in str(exc)
    else:
        raise AssertionError("Expected duplicate session binding to fail")
