from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from .device_model_sync import (
    build_protocols_by_unique_id,
    select_unique_catalog_model,
    sync_device_models_from_traccar,
)
from .traccar_api import TraccarAPIError, traccar_device_positions, traccar_devices


@override_settings(
    TRACCAR_API_URL="http://127.0.0.1:8082/api",
    TRACCAR_API_USERNAME="reader",
    TRACCAR_API_PASSWORD="test-secret",
)
class TraccarAPIClientTests(SimpleTestCase):
    @patch("fleet.traccar_api.urlopen")
    def test_devices_request_uses_basic_auth_and_parses_json(self, urlopen):
        response = MagicMock()
        response.read.return_value = b'[{"id": 7, "uniqueId": "352016703005868"}]'
        response.__enter__.return_value = response
        urlopen.return_value = response

        result = traccar_devices()

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8082/api/devices")
        self.assertTrue(request.get_header("Authorization").startswith("Basic "))
        self.assertEqual(result[0]["uniqueId"], "352016703005868")

    @patch("fleet.traccar_api.urlopen")
    def test_history_request_includes_device_and_time_range(self, urlopen):
        response = MagicMock()
        response.read.return_value = b'[]'
        response.__enter__.return_value = response
        urlopen.return_value = response

        result = traccar_device_positions(
            42, "2026-10-21T07:00:00Z", "2026-10-21T08:00:00Z"
        )

        url = urlopen.call_args.args[0].full_url
        self.assertIn("deviceId=42", url)
        self.assertIn("from=2026-10-21T07%3A00%3A00Z", url)
        self.assertIn("to=2026-10-21T08%3A00%3A00Z", url)
        self.assertEqual(result, [])

    @override_settings(
        TRACCAR_API_URL="http://127.0.0.1:8082/api",
        TRACCAR_API_USERNAME="",
        TRACCAR_API_PASSWORD="",
    )
    def test_missing_credentials_fail_closed(self):
        with self.assertRaises(TraccarAPIError):
            traccar_devices()


class DeviceModelSyncTests(SimpleTestCase):
    def _model(self, manufacturer, name, protocol, pk=None):
        return SimpleNamespace(manufacturer=manufacturer, name=name, protocol=protocol, pk=pk)

    def test_protocol_map_uses_position_protocol_keyed_by_unique_id(self):
        devices = [
            {"id": 5, "uniqueId": "352016703005868"},
            {"id": 6, "uniqueId": " 862123456789012 "},
            {"id": 7, "uniqueId": ""},
        ]
        positions = [
            {"deviceId": 5, "protocol": "Teltonika"},
            {"deviceId": 6, "protocol": "gt06"},
            {"deviceId": 7, "protocol": "gt06"},
            {"deviceId": 5, "protocol": "unknown"},
        ]

        result = build_protocols_by_unique_id(devices, positions)

        self.assertEqual(
            result,
            {"352016703005868": "teltonika", "862123456789012": "gt06"},
        )

    def test_protocol_map_falls_back_to_device_protocol(self):
        result = build_protocols_by_unique_id(
            [{"id": 1, "uniqueId": "111", "protocol": "H02"}],
            [],
        )

        self.assertEqual(result, {"111": "h02"})

    def test_unique_model_is_selected_for_unambiguous_protocol(self):
        catalog = [self._model("Queclink", "GV300", "queclink")]

        model = select_unique_catalog_model("Queclink", catalog)

        self.assertIsNotNone(model)
        self.assertEqual(model.name, "GV300")

    def test_shared_protocol_stays_unresolved(self):
        catalog = [
            self._model("Concox", "GT06N", "gt06"),
            self._model("Jimi IoT", "VL03", "gt06"),
        ]

        self.assertIsNone(select_unique_catalog_model("gt06", catalog))

    def test_duplicate_catalog_rows_of_same_model_are_not_ambiguous(self):
        catalog = [
            self._model("Teltonika", "FMB965", "teltonika"),
            self._model("Teltonika", "FMB965", "teltonika"),
        ]

        model = select_unique_catalog_model("teltonika", catalog)

        self.assertEqual(model.name, "FMB965")

    def test_placeholder_protocols_are_never_resolved(self):
        catalog = [self._model("Other / generic", "GT06", "clones")]

        self.assertIsNone(select_unique_catalog_model("", catalog))
        self.assertIsNone(select_unique_catalog_model("unknown", catalog))
        self.assertIsNone(select_unique_catalog_model("clones", catalog))

    def _sync_fixture(self):
        catalog = [
            self._model("Queclink", "GV300", "queclink", pk=1),
            self._model("Concox", "GT06N", "gt06", pk=2),
            self._model("Jimi IoT", "VL03", "gt06", pk=3),
        ]
        devices = [
            SimpleNamespace(imei="111", device_model=None, save=MagicMock()),
            SimpleNamespace(
                imei="222",
                device_model=self._model("Teltonika", "FMB965", "teltonika", pk=4),
                save=MagicMock(),
            ),
            SimpleNamespace(imei="333", device_model=None, save=MagicMock()),
        ]
        traccar_devices = [
            {"id": 1, "uniqueId": "111"},
            {"id": 2, "uniqueId": "222"},
            {"id": 3, "uniqueId": "333"},
        ]
        traccar_positions = [
            {"deviceId": 1, "protocol": "queclink"},
            {"deviceId": 2, "protocol": "queclink"},
            {"deviceId": 3, "protocol": "gt06"},
        ]
        return catalog, devices, traccar_devices, traccar_positions

    def test_dry_run_reports_changes_without_writing(self):
        catalog, devices, payload_devices, payload_positions = self._sync_fixture()

        result = sync_device_models_from_traccar(
            dry_run=True,
            traccar_devices_payload=payload_devices,
            traccar_positions_payload=payload_positions,
            catalog=catalog,
            devices=devices,
        )

        self.assertEqual(result["assigned"], 1)
        self.assertEqual(result["corrected"], 1)
        self.assertEqual(result["unresolved"], 1)
        self.assertIsNone(devices[0].device_model)
        devices[0].save.assert_not_called()

    def test_sync_writes_blank_and_corrects_mismatched_models(self):
        catalog, devices, payload_devices, payload_positions = self._sync_fixture()

        result = sync_device_models_from_traccar(
            traccar_devices_payload=payload_devices,
            traccar_positions_payload=payload_positions,
            catalog=catalog,
            devices=devices,
        )

        self.assertEqual(result["assigned"], 1)
        self.assertEqual(result["corrected"], 1)
        self.assertEqual(devices[0].device_model.pk, 1)
        self.assertEqual(devices[1].device_model.pk, 1)
        devices[0].save.assert_called_once_with(update_fields=["device_model", "updated_at"])
        devices[2].save.assert_not_called()

    def test_placeholder_registered_protocol_is_corrected(self):
        catalog = [self._model("Queclink", "GV300", "queclink", pk=1)]
        devices = [
            SimpleNamespace(
                imei="111",
                device_model=self._model("Other / generic", "GT06", "clones", pk=9),
                save=MagicMock(),
            )
        ]

        result = sync_device_models_from_traccar(
            traccar_devices_payload=[{"id": 1, "uniqueId": "111"}],
            traccar_positions_payload=[{"deviceId": 1, "protocol": "queclink"}],
            catalog=catalog,
            devices=devices,
        )

        self.assertEqual(result["corrected"], 1)
        self.assertEqual(devices[0].device_model.pk, 1)
