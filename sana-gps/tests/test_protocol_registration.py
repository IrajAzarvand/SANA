from unittest.mock import Mock

from app.protocols.registration import confirm_detected_protocol
from app.repositories.device import DeviceRecord


def _device(*, effective_protocol: str = "", device_protocol: str = "") -> DeviceRecord:
    return DeviceRecord(
        id=17,
        imei="352094082300754",
        management_status="warehouse",
        protocol=effective_protocol,
        data_active=True,
        device_protocol=device_protocol,
    )


def test_shared_policy_persists_any_future_protocol_for_blank_device() -> None:
    repository = Mock()
    repository.set_detected_protocol.return_value = True

    assert confirm_detected_protocol(repository, _device(), "  future-protocol ") is True

    repository.set_detected_protocol.assert_called_once_with(17, "future-protocol")


def test_shared_policy_does_not_rewrite_an_already_matching_device_protocol() -> None:
    repository = Mock()

    assert confirm_detected_protocol(
        repository,
        _device(effective_protocol="teltonika", device_protocol="teltonika"),
        "teltonika",
    ) is True

    repository.set_detected_protocol.assert_not_called()


def test_shared_policy_rejects_a_model_or_device_protocol_mismatch() -> None:
    repository = Mock()

    assert confirm_detected_protocol(
        repository,
        _device(effective_protocol="gt06"),
        "future-protocol",
    ) is False

    repository.set_detected_protocol.assert_not_called()


def test_shared_policy_rejects_concurrent_conflict_reported_by_repository() -> None:
    repository = Mock()
    repository.set_detected_protocol.return_value = False

    assert confirm_detected_protocol(repository, _device(), "teltonika") is False

    repository.set_detected_protocol.assert_called_once_with(17, "teltonika")


def test_shared_policy_rejects_empty_protocol() -> None:
    repository = Mock()

    assert confirm_detected_protocol(repository, _device(), " ") is False

    repository.set_detected_protocol.assert_not_called()
