from unittest.mock import Mock

from app.traccar.device_sync import sync_devices_once


def test_sync_creates_missing_sana_devices_and_mirrors_traccar_position_protocols():
    client = Mock()
    client.list_devices.return_value = [{"id": 10, "uniqueId": "imei-1"}]
    client.create_device.return_value = {"id": 11, "uniqueId": "imei-2"}
    client.list_current_positions.return_value = [
        {"deviceId": 10, "protocol": "teltonika"},
        {"deviceId": 11, "protocol": "gt06"},
        {"deviceId": 999, "protocol": "unknown"},
        {"deviceId": 10, "protocol": ""},
    ]
    repository = Mock()
    repository.find_all_identifiers.return_value = ("imei-1", "imei-2")

    assert sync_devices_once(client, repository) == 1

    client.create_device.assert_called_once_with("imei-2")
    repository.set_traccar_protocol.assert_any_call("imei-1", "teltonika")
    repository.set_traccar_protocol.assert_any_call("imei-2", "gt06")
    assert repository.set_traccar_protocol.call_count == 2


def test_sync_ignores_positions_without_protocol_or_unregistered_unique_ids():
    client = Mock()
    client.list_devices.return_value = [{"id": 10, "uniqueId": "imei-1"}]
    client.list_current_positions.return_value = [
        {"deviceId": 10, "protocol": ""},
        {"deviceId": 99, "protocol": "gt06"},
    ]
    repository = Mock()
    repository.find_all_identifiers.return_value = ("imei-1",)

    assert sync_devices_once(client, repository) == 0
    repository.set_traccar_protocol.assert_not_called()
