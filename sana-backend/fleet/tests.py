from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from django.utils.dateparse import parse_datetime
from rest_framework.test import APIRequestFactory, force_authenticate
from types import SimpleNamespace

from .traccar_api import TraccarAPIError, traccar_device_positions, traccar_devices
from .views import (
    DeviceViewSet,
    normalize_traccar_history_positions,
    parse_report_history_cursor,
    traccar_position_timestamp,
)
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
        filter_models.return_value.annotate.return_value.filter.return_value.only.return_value = [catalog_model]
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
        filter_models.return_value.annotate.return_value.filter.return_value.only.return_value = [catalog_model]
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

    def test_raw_traccar_model_is_exposed_without_catalog_match(self):
        device = SimpleNamespace(traccar_model='Queclink GV300')
        self.assertEqual(
            self.serializer.get_traccar_model(device),
            'Queclink GV300',
        )

    def test_raw_traccar_model_is_empty_when_traccar_does_not_report_one(self):
        device = SimpleNamespace()
        self.assertIsNone(self.serializer.get_traccar_model(device))

    def test_active_subscription_link_uses_prefetched_links_and_is_cached(self):
        active_link = SimpleNamespace(unassigned_at=None, subscription_id=12)
        older_link = SimpleNamespace(unassigned_at=None, subscription_id=8)
        device = SimpleNamespace(
            management_status='active',
            _prefetched_subscription_links=[active_link, older_link],
        )

        self.assertIs(self.serializer._active_subscription_link(device), active_link)
        self.assertIs(self.serializer._active_subscription_link(device), active_link)

    def test_historical_subscription_links_are_not_displayed_as_current_contract(self):
        latest = SimpleNamespace(unassigned_at=object(), subscription_id=12)
        older = SimpleNamespace(unassigned_at=object(), subscription_id=8)
        device = SimpleNamespace(
            management_status='warehouse',
            _prefetched_subscription_links=[latest, older],
        )

        self.assertIsNone(self.serializer._display_subscription_link(device))
        self.assertIsNone(self.serializer._display_subscription_link(device))

    def test_ended_or_unassigned_contract_is_not_displayed(self):
        subscription = SimpleNamespace(computed_status='active')
        ended_link = SimpleNamespace(
            unassigned_at=object(),
            is_active=False,
            subscription=subscription,
        )
        device = SimpleNamespace(
            management_status='active',
            _prefetched_subscription_links=[ended_link],
        )

        self.assertIsNone(self.serializer._display_subscription_link(device))

    def test_expired_contract_is_not_displayed_even_if_assignment_is_open(self):
        subscription = SimpleNamespace(computed_status='expired')
        link = SimpleNamespace(
            unassigned_at=None,
            is_active=False,
            subscription=subscription,
        )
        device = SimpleNamespace(
            management_status='active',
            _prefetched_subscription_links=[link],
        )

        self.assertIsNone(self.serializer._display_subscription_link(device))

    def test_current_valid_contract_is_displayed(self):
        subscription = SimpleNamespace(
            id=12,
            contract_number='ORG-1405-0012',
            computed_status='active',
        )
        link = SimpleNamespace(
            unassigned_at=None,
            is_active=True,
            subscription=subscription,
        )
        device = SimpleNamespace(
            management_status='active',
            _prefetched_subscription_links=[link],
        )

        self.assertIs(self.serializer._display_subscription_link(device), link)
        self.assertEqual(self.serializer.get_subscription_number(device), 'ORG-1405-0012')

    def test_legacy_replacement_operation_does_not_create_a_current_contract(self):
        operation = SimpleNamespace(subscription_id=12)
        device = SimpleNamespace(
            management_status='faulty',
            _prefetched_subscription_links=[],
            _prefetched_replacement_source_operations=[operation],
            _prefetched_replacement_target_operations=[],
        )

        self.assertIsNone(self.serializer._display_subscription_link(device))

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
        subscription = SimpleNamespace(computed_status='active')
        active_link = SimpleNamespace(
            unassigned_at=None, is_active=True, subscription=subscription
        )
        device = SimpleNamespace(
            management_status='active',
            _prefetched_subscription_links=[active_link],
            _prefetched_replacement_target_operations=[],
        )

        self.assertFalse(self.serializer.get_is_in_warehouse(device))
        self.assertTrue(self.serializer.get_data_active(device))
        self.assertEqual(self.serializer.get_management_status(device), 'active')

    def test_data_service_is_inactive_when_contract_is_suspended_or_expired(self):
        for contract_status in ('suspended', 'cancelled', 'expired', 'pending'):
            with self.subTest(contract_status=contract_status):
                subscription = SimpleNamespace(computed_status=contract_status)
                active_link = SimpleNamespace(
                    unassigned_at=None, is_active=True, subscription=subscription
                )
                device = SimpleNamespace(
                    management_status='active',
                    _prefetched_subscription_links=[active_link],
                    _prefetched_replacement_target_operations=[],
                )
                self.assertFalse(self.serializer.get_data_active(device))

    def test_customer_name_prefers_current_contract_customer(self):
        subscription = SimpleNamespace(
            computed_status='active',
            get_customer_name=lambda: 'مشتری قرارداد'
        )
        active_link = SimpleNamespace(
            unassigned_at=None, is_active=True, subscription=subscription
        )
        device = SimpleNamespace(
            _prefetched_subscription_links=[active_link],
            current_holder_organization=None,
            current_holder_user=None,
            organization=None,
            owner_user=None,
        )

        self.assertEqual(
            self.serializer.get_customer_name(device),
            'مشتری قرارداد',
        )


class TraccarPositionTimestampTests(SimpleTestCase):
    def test_server_time_is_preferred_over_unreliable_device_clock(self):
        position = {
            "serverTime": "2026-10-31T08:00:00Z",
            "fixTime": "2026-10-31T07:58:00Z",
            "deviceTime": "2026-10-31T07:57:00Z",
        }

        result = traccar_position_timestamp(position)

        self.assertEqual(result.isoformat(), "2026-10-31T08:00:00+00:00")

    def test_missing_server_time_does_not_fall_back_to_device_clock(self):
        position = {
            "fixTime": "2026-10-31T07:58:00Z",
            "deviceTime": "2026-10-31T07:57:00Z",
        }

        self.assertIsNone(traccar_position_timestamp(position))


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

 

class TraccarHistoryIntegrityTests(SimpleTestCase):
    def setUp(self):
        self.start = parse_datetime("2026-11-01T00:00:00Z")
        self.end = parse_datetime("2026-11-02T00:00:00Z")

    def position(self, point_id, server_time, latitude=35.7, longitude=51.4, **extra):
        return {
            "id": point_id,
            "serverTime": server_time,
            "latitude": latitude,
            "longitude": longitude,
            **extra,
        }

    def test_history_is_sorted_by_server_time_and_duplicate_position_ids_are_removed(self):
        positions = [
            self.position(12, "2026-11-01T10:02:00Z"),
            self.position(11, "2026-11-01T10:01:00Z"),
            self.position(11, "2026-11-01T10:01:00Z", latitude=0, longitude=0),
        ]

        result = normalize_traccar_history_positions(positions, self.start, self.end)

        self.assertEqual([row[1] for row in result], [11, 12])
        self.assertEqual(result[0][3:], (35.7, 51.4))

    def test_history_rejects_missing_server_time_and_invalid_coordinates(self):
        positions = [
            self.position(1, None),
            self.position(2, "2026-11-01T10:00:00Z", latitude=91),
            self.position(3, "2026-11-01T10:00:00Z", longitude=181),
            self.position(4, "2026-11-01T10:00:00Z", latitude=float("nan")),
            self.position(5, "2026-11-03T10:00:00Z"),
        ]

        self.assertEqual(
            normalize_traccar_history_positions(positions, self.start, self.end),
            [],
        )

    def test_history_cursor_uses_server_time_and_position_id_as_tiebreaker(self):
        cursor_time = parse_datetime("2026-11-01T10:00:00Z")
        positions = [
            self.position(10, "2026-11-01T10:00:00Z"),
            self.position(11, "2026-11-01T10:00:00Z"),
            self.position(12, "2026-11-01T10:01:00Z"),
        ]

        result = normalize_traccar_history_positions(
            positions, self.start, self.end, cursor_time=cursor_time, cursor_id=10,
        )

        self.assertEqual([row[1] for row in result], [11, 12])

    def test_cursor_rejects_invalid_or_incomplete_values(self):
        for raw_time, raw_id in (
            ("not-a-date", "12"),
            ("2026-11-01T10:00:00Z", "bad"),
            ("2026-11-01T10:00:00Z", "0"),
            (None, "12"),
        ):
            with self.subTest(raw_time=raw_time, raw_id=raw_id):
                with self.assertRaises(ValueError):
                    parse_report_history_cursor(raw_time, raw_id)

    def test_empty_cursor_is_valid_for_first_page(self):
        self.assertEqual(parse_report_history_cursor(None, None), (None, 0))


class ReportHistoryRequestSecurityTests(SimpleTestCase):
    def test_non_numeric_device_id_is_rejected_before_queryset_access(self):
        factory = APIRequestFactory()
        request = factory.get("/api/devices/report-history/", {"device_id": "not-an-id"})
        force_authenticate(
            request,
            user=SimpleNamespace(is_authenticated=True, is_site_admin=True),
        )

        response = DeviceViewSet.as_view({"get": "report_history"})(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "شناسه دستگاه نامعتبر است.")

    def test_non_positive_device_id_is_rejected_before_queryset_access(self):
        factory = APIRequestFactory()
        request = factory.get("/api/devices/report-history/", {"device_id": "0"})
        force_authenticate(
            request,
            user=SimpleNamespace(is_authenticated=True, is_site_admin=True),
        )

        response = DeviceViewSet.as_view({"get": "report_history"})(request)

        self.assertEqual(response.status_code, 400)
