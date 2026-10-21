from uuid import uuid4
from unittest.mock import MagicMock

from app.repositories.unknown_protocol_queue import UnknownProtocolQueueRepository


def test_unknown_device_payloads_are_never_stored_in_sana():
    pool = MagicMock()
    repository = UnknownProtocolQueueRepository(pool)

    assert repository.record_chunk(
        session_id=uuid4(),
        transport="tcp",
        remote_address=("192.0.2.10", 50123),
        payload=b"raw-packet",
    ) is False
    assert repository.match_pending_sessions(("9176515720",)) == 0
    assert repository.check_schema() is False
    pool.connection.assert_not_called()
