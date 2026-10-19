from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

from app.traccar.position_receiver import TraccarPositionReceiver


def make_receiver():
    client = Mock()
    client.get_device_by_id.return_value = {"id": 42, "uniqueId": "352016702941683"}
    devices = Mock()
    devices.find_by_imei.return_value = SimpleNamespace(id=7, imei="352016702941683")
    telemetry = Mock()
    receiver = TraccarPositionReceiver(
        client=client,
        device_repository=devices,
        telemetry_repository=telemetry,
    )
    return receiver, client, devices, telemetry


def position():
    return {
        "id": 1001,
        "deviceId": 42,
        "protocol": "teltonika",
        "fixTime": "2026-10-19T10:25:30.000Z",
        "deviceTime": "2026-10-19T10:25:30.000Z",
        "serverTime": "2026-10-19T10:25:31.000Z",
        "valid": True,
        "latitude": 37.13023,
        "longitude": 47.59278,
        "speed": 10,
        "course": 361,
        "altitude": 120,
        "attributes": {"ignition": True},
    }


def test_accepts_traccar_json_position_device_envelope_and_normalizes_data():
    receiver, client, devices, telemetry = make_receiver()
    payload = {
        "position": position(),
        "device": {"id": 42, "name": "tracker", "uniqueId": "352016702941683"},
    }

    result = receiver.receive_payload(payload)

    assert result == {"received": 1, "saved": 1, "unknown": 0, "invalid": 0}
    client.get_device_by_id.assert_called_once_with(42)
    devices.find_by_imei.assert_called_once_with("352016702941683")
    telemetry.save_batch.assert_called_once()
    records = telemetry.save_batch.call_args.args[0]
    assert len(records) == 1
    record = records[0]
    assert record.device_id == 7  # SANA ID, not Traccar's internal ID 42
    assert record.device_time == datetime(2026, 10, 19, 10, 25, 30, tzinfo=timezone.utc)
    assert record.latitude == Decimal("37.13023")
    assert record.longitude == Decimal("47.59278")
    assert record.speed == Decimal("18.520")
    assert record.heading == Decimal("1")
    assert record.gps_valid is True
    assert record.attributes["source"] == "traccar-json"
    assert telemetry.save_batch.call_args.kwargs["protocol"] == "traccar-json"


def test_still_accepts_bare_traccar_position_payload():
    receiver, _, _, telemetry = make_receiver()

    result = receiver.receive_payload(position())

    assert result == {"received": 1, "saved": 1, "unknown": 0, "invalid": 0}
    telemetry.save_batch.assert_called_once()


def test_rejects_mismatched_device_and_position_ids():
    receiver, client, _, telemetry = make_receiver()
    payload = {
        "position": position(),
        "device": {"id": 999, "uniqueId": "352016702941683"},
    }

    result = receiver.receive_payload(payload)

    assert result == {"received": 1, "saved": 0, "unknown": 0, "invalid": 1}
    client.get_device_by_id.assert_not_called()
    telemetry.save_batch.assert_not_called()


def test_unknown_registered_mapping_does_not_save_telemetry():
    receiver, _, devices, telemetry = make_receiver()
    devices.find_by_imei.return_value = None

    result = receiver.receive_payload({"position": position(), "device": {"id": 42}})

    assert result == {"received": 1, "saved": 0, "unknown": 1, "invalid": 0}
    telemetry.save_batch.assert_not_called()
