from __future__ import annotations

from unittest.mock import MagicMock, Mock

from app.repositories.device import DeviceRepository


def make_repository():
    connection = Mock()
    pool = MagicMock()
    pool.connection.return_value.__enter__.return_value = connection
    return DeviceRepository(pool), connection, pool


def test_find_all_identifiers_reads_only_registered_imei_values():
    repository, connection, _ = make_repository()
    connection.execute.return_value.fetchall.return_value = [("123",), ("456",)]
    assert repository.find_all_identifiers() == ("123", "456")
    sql = connection.execute.call_args.args[0].lower()
    assert sql.strip().startswith("select imei from public.fleet_device")


def test_protocol_is_mirrored_from_traccar_for_matching_registered_imei():
    repository, connection, _ = make_repository()
    connection.execute.return_value.fetchone.return_value = (42,)
    assert repository.set_traccar_protocol(" 352094082143253 ", " TELTONIKA ") is True
    sql, params = connection.execute.call_args.args
    assert "update public.fleet_device" in sql.lower()
    assert "returning id" in sql.lower()
    assert params == ("teltonika", "352094082143253", "teltonika")


def test_protocol_sync_does_not_write_empty_or_overlong_values():
    repository, _, pool = make_repository()
    assert repository.set_traccar_protocol("123", "") is False
    assert repository.set_traccar_protocol("123", "x" * 51) is False
    pool.connection.assert_not_called()


def test_protocol_sync_returns_false_when_protocol_is_already_current():
    repository, connection, _ = make_repository()
    connection.execute.return_value.fetchone.return_value = None
    assert repository.set_traccar_protocol("123", "teltonika") is False
