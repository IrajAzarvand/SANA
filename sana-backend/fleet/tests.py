from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from .traccar_api import TraccarAPIError, traccar_device_positions, traccar_devices
from .views import DeviceViewSet, traccar_position_timestamp
from .serializers import DeviceListSerializer


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



class TraccarDeviceModelSyncTests(SimpleTestCase):
    def make_device(self, imei, model_id=None):
        device = MagicMock()
        device.imei = imei
        device.device_model_id = model_id
        device.device_model = None
        device.save = MagicMock()
        return device

    @patch("fleet.views.DeviceModel.objects.filter")
    def test_exact_traccar_model_fills_missing_sana_model(self, filter_models):
        catalog_model = SimpleNamespace(
            id=12, manufacturer="Teltonika", name="FMB920"
        )
        filter_models.return_value.only.return_value = [catalog_model]
        device = self.make_device("352016703005868")
        traccar = {
            "352016703005868": {
                "uniqueId": "352016703005868",
                "model": "Teltonika FMB920",
                "name": "Truck 01",
            }
        }

        DeviceViewSet._sync_models_from_traccar([device], traccar)

        self.assertEqual(device.device_model, catalog_model)
        device.save.assert_called_once_with(update_fields=["device_model", "updated_at"])

    @patch("fleet.views.DeviceModel.objects.filter")
    def test_missing_or_unmatched_traccar_model_does_not_guess_from_name(self, filter_models):
        catalog_model = SimpleNamespace(
            id=12, manufacturer="Teltonika", name="FMB920"
        )
        filter_models.return_value.only.return_value = [catalog_model]
        device = self.make_device("352016703005868", model_id=99)
        traccar = {
            "352016703005868": {
                "uniqueId": "352016703005868",
                "model": "",
                "name": "Teltonika FMB920",
            }
        }

        DeviceViewSet._sync_models_from_traccar([device], traccar)

        self.assertEqual(device.device_model_id, 99)
        device.save.assert_not_called()


class DeviceListSerializerPrefetchTests(SimpleTestCase):
    def setUp(self):
        self.serializer = DeviceListSerializer()

    def test_active_subscription_link_uses_prefetched_links_and_is_cached(self):
        active_link = SimpleNamespace(unassigned_at=None, subscription_id=12)
        older_link = SimpleNamespace(unassigned_at=None, subscription_id=8)
        device = SimpleNamespace(
            management_status='active',
            _prefetched_subscription_links=[active_link, older_link],
        )

        self.assertIs(self.serializer._active_subscription_link(device), active_link)
        self.assertIs(self.serializer._active_subscription_link(device), active_link)

    def test_latest_historical_subscription_link_is_used_when_no_active_link_exists(self):
        latest = SimpleNamespace(unassigned_at=object(), subscription_id=12)
        older = SimpleNamespace(unassigned_at=object(), subscription_id=8)
        device = SimpleNamespace(
            management_status='warehouse',
            _prefetched_subscription_links=[latest, older],
            _prefetched_replacement_source_operations=[],
            _prefetched_replacement_target_operations=[],
        )

        self.assertIs(self.serializer._display_subscription_link(device), latest)
        self.assertIs(self.serializer._display_subscription_link(device), latest)

    def test_replacement_operation_fallback_uses_prefetched_source_operations(self):
        operation = SimpleNamespace(subscription_id=12)
        device = SimpleNamespace(
            management_status='faulty',
            _prefetched_subscription_links=[],
            _prefetched_replacement_source_operations=[operation],
            _prefetched_replacement_target_operations=[],
        )

        self.assertIs(self.serializer._display_subscription_link(device), operation)

    def test_current_replacement_operation_matches_active_subscription(self):
        active_link = SimpleNamespace(unassigned_at=None, subscription_id=12)
        old_operation = SimpleNamespace(
            operation_type='return_for_repair',
            subscription_id=8,
        )
        current_operation = SimpleNamespace(
            operation_type='return_for_repair',
            subscription_id=12,
        )
        device = SimpleNamespace(
            management_status='installed',
            _prefetched_subscription_links=[active_link],
            _prefetched_replacement_target_operations=[
                old_operation, current_operation,
            ],
        )

        self.assertIs(
            self.serializer._current_replacement_operation(device),
            current_operation,
        )

    def test_warehouse_and_data_status_reuse_prefetched_active_link(self):
        active_link = SimpleNamespace(unassigned_at=None, is_active=True)
        device = SimpleNamespace(
            management_status='active',
            _prefetched_subscription_links=[active_link],
        )

        self.assertFalse(self.serializer.get_is_in_warehouse(device))
        self.assertTrue(self.serializer.get_data_active(device))
        self.assertEqual(self.serializer.get_management_status(device), 'active')


class TraccarPositionTimestampTests(SimpleTestCase):
    def test_server_time_is_preferred_over_unreliable_device_clock(self):
        position = {
            "serverTime": "2026-10-31T08:00:00Z",
            "fixTime": "2026-10-31T07:58:00Z",
            "deviceTime": "2026-10-31T07:57:00Z",
        }

        result = traccar_position_timestamp(position)

        self.assertEqual(result.isoformat(), "2026-10-31T08:00:00+00:00")

    def test_device_timestamps_are_fallbacks_when_server_time_is_missing(self):
        position = {
            "fixTime": "2026-10-31T07:58:00Z",
            "deviceTime": "2026-10-31T07:57:00Z",
        }

        result = traccar_position_timestamp(position)

        self.assertEqual(result.isoformat(), "2026-10-31T07:58:00+00:00")


class TraccarAPIClientFailureTests(SimpleTestCase):
    @patch("fleet.traccar_api.urlopen")
    def test_http_error_is_converted_to_safe_api_error(self, urlopen):
        urlopen.side_effect = HTTPError(
            "http://127.0.0.1:8082/api/devices", 401, "Unauthorized", {}, None
        )

        with self.assertRaisesRegex(TraccarAPIError, "HTTP 401"):
            traccar_devices()

    @patch("fleet.traccar_api.urlopen")
    def test_invalid_json_is_converted_to_api_error(self, urlopen):
        response = MagicMock()
        response.read.return_value = b"{not-json"
        response.__enter__.return_value = response
        urlopen.return_value = response

        with self.assertRaisesRegex(TraccarAPIError, "JSONDecodeError"):
            traccar_devices()

    @patch("fleet.traccar_api.urlopen")
    def test_network_error_is_converted_to_api_error(self, urlopen):
        urlopen.side_effect = URLError("connection refused")

        with self.assertRaisesRegex(TraccarAPIError, "URLError"):
            traccar_devices()
