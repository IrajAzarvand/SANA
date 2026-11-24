from datetime import date, datetime, timedelta
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from organizations.models import Branch, Organization, Subscription, SubscriptionDevice
from .models import Device, DeviceAlertState, DeviceCustomerAccessPeriod, DeviceLifecycleEvent
from types import SimpleNamespace

from .traccar_api import TraccarAPIError, traccar_device_events, traccar_device_positions, traccar_devices
from .views import (
    DeviceViewSet,
    DeviceLifecycleEventViewSet,
    normalize_traccar_history_positions,
    parse_report_history_cursor,
    traccar_history_device_id,
    traccar_position_protocol,
    traccar_position_timestamp,
)
from .serializers import DeviceListSerializer


class TraccarHistoryDeviceIdCacheTests(SimpleTestCase):
    @patch("fleet.views.traccar_device_by_unique_id")
    @patch("fleet.views.cache")
    def test_cached_device_id_avoids_repeated_traccar_lookup(self, cache_mock, lookup):
        cache_mock.get.return_value = 42
        self.assertEqual(traccar_history_device_id("860000000000107"), 42)
        lookup.assert_not_called()
        cache_mock.get.assert_called_once_with(
            "sana:traccar:history-device-id:860000000000107"
        )

    @patch("fleet.views.traccar_device_by_unique_id")
    @patch("fleet.views.cache")
    def test_device_id_lookup_is_cached_for_short_period(self, cache_mock, lookup):
        cache_mock.get.return_value = None
        lookup.return_value = {"id": 42, "uniqueId": "860000000000107"}
        self.assertEqual(traccar_history_device_id("860000000000107"), 42)
        lookup.assert_called_once_with("860000000000107")
        cache_mock.set.assert_called_once_with(
            "sana:traccar:history-device-id:860000000000107", 42, timeout=120
        )

    @patch("fleet.views.traccar_device_by_unique_id")
    @patch("fleet.views.cache")
    def test_missing_traccar_device_is_not_cached(self, cache_mock, lookup):
        cache_mock.get.return_value = None
        lookup.return_value = None
        self.assertIsNone(traccar_history_device_id("860000000000107"))
        cache_mock.set.assert_not_called()


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

    @patch("fleet.traccar_api.urlopen")
    def test_device_lookup_filters_by_unique_id(self, urlopen):
        response = MagicMock()
        response.read.return_value = b'[{"id": 42, "uniqueId": "860000000000107"}]'
        response.__enter__.return_value = response
        urlopen.return_value = response

        from .traccar_api import traccar_device_by_unique_id
        result = traccar_device_by_unique_id("860000000000107")

        self.assertEqual(result["id"], 42)
        self.assertIn("uniqueId=860000000000107", urlopen.call_args.args[0].full_url)

    @patch("fleet.traccar_api.urlopen")
    def test_events_request_uses_device_and_time_range(self, urlopen):
        response = MagicMock()
        response.read.return_value = b'[{"id": 9, "type": "deviceOffline"}]'
        response.__enter__.return_value = response
        urlopen.return_value = response

        result = traccar_device_events(
            42, "2026-11-01T00:00:00Z", "2026-11-02T00:00:00Z"
        )

        url = urlopen.call_args.args[0].full_url
        self.assertIn("/reports/events?", url)
        self.assertIn("deviceId=42", url)
        self.assertIn("from=2026-11-01T00%3A00%3A00Z", url)
        self.assertIn("to=2026-11-02T00%3A00%3A00Z", url)
        self.assertEqual(result[0]["type"], "deviceOffline")

    @patch("fleet.traccar_api.urlopen")
    def test_history_request_includes_server_side_limit(self, urlopen):
        response = MagicMock()
        response.read.return_value = b'[]'
        response.__enter__.return_value = response
        urlopen.return_value = response

        traccar_device_positions(
            42, "2026-10-21T07:00:00Z", "2026-10-21T08:00:00Z", limit=5001
        )

        self.assertIn("limit=5001", urlopen.call_args.args[0].full_url)


    @override_settings(
        TRACCAR_API_URL="http://127.0.0.1:8082/api",
        TRACCAR_API_USERNAME="",
        TRACCAR_API_PASSWORD="",
    )
    def test_missing_credentials_fail_closed(self):
        with self.assertRaises(TraccarAPIError):
            traccar_devices()



    @patch("fleet.traccar_api.urlopen")
    def test_events_request_supports_multiple_device_ids(self, urlopen):
        response = MagicMock()
        response.read.return_value = b'[]'
        response.__enter__.return_value = response
        urlopen.return_value = response

        traccar_device_events(
            [42, 43], "2026-11-01T00:00:00Z", "2026-11-02T00:00:00Z"
        )

        url = urlopen.call_args.args[0].full_url
        self.assertIn("deviceId=42", url)
        self.assertIn("deviceId=43", url)


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

    def test_live_traccar_protocol_is_exposed_for_device_list(self):
        device = SimpleNamespace(traccar_protocol='teltonika')
        self.assertEqual(
            self.serializer.get_traccar_protocol(device),
            'teltonika',
        )

    def test_live_traccar_protocol_is_empty_when_no_position_protocol_exists(self):
        device = SimpleNamespace()
        self.assertIsNone(self.serializer.get_traccar_protocol(device))

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

    def test_inactive_reason_reports_missing_contract(self):
        device = SimpleNamespace(
            management_status='warehouse',
            _prefetched_subscription_links=[],
        )
        self.assertEqual(
            self.serializer.get_data_inactive_reason(device),
            'دستگاه به هیچ قراردادی متصل نیست',
        )

    @patch('fleet.serializers.timezone.localdate', return_value=date(2026, 11, 6))
    def test_inactive_reason_reports_assignment_date_before_contract_status(self, _today):
        link = SimpleNamespace(
            unassigned_at=None,
            is_active=False,
            start_date=date(2026, 11, 7),
            end_date=date(2026, 12, 1),
            subscription=SimpleNamespace(computed_status='suspended'),
        )
        device = SimpleNamespace(
            management_status='active',
            _prefetched_subscription_links=[link],
        )
        self.assertEqual(
            self.serializer.get_data_inactive_reason(device),
            'تاریخ شروع تخصیص دستگاه هنوز نرسیده',
        )

    def test_inactive_reason_reports_contract_status_before_management_status(self):
        link = SimpleNamespace(
            unassigned_at=None,
            is_active=True,
            subscription=SimpleNamespace(computed_status='suspended'),
        )
        device = SimpleNamespace(
            management_status='faulty',
            _prefetched_subscription_links=[link],
        )
        self.assertEqual(
            self.serializer.get_data_inactive_reason(device),
            'قرارداد تعلیق شده است',
        )

    def test_inactive_reason_reports_management_status(self):
        link = SimpleNamespace(
            unassigned_at=None,
            is_active=True,
            subscription=SimpleNamespace(computed_status='active'),
        )
        device = SimpleNamespace(
            management_status='faulty',
            _prefetched_subscription_links=[link],
        )
        self.assertEqual(
            self.serializer.get_data_inactive_reason(device),
            'دستگاه خراب است',
        )

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
    def test_position_protocol_is_normalized_from_traccar_decoder_metadata(self):
        self.assertEqual(
            traccar_position_protocol({"protocol": "  Teltonika  "}),
            "teltonika",
        )

    def test_missing_position_protocol_remains_unknown(self):
        self.assertEqual(traccar_position_protocol({"protocol": ""}), "")

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


@override_settings(
    TRACCAR_API_URL="http://127.0.0.1:8082/api",
    TRACCAR_API_USERNAME="reader",
    TRACCAR_API_PASSWORD="test-secret",
)
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
            user=SimpleNamespace(pk=1, is_authenticated=True, is_site_admin=True),
        )

        response = DeviceViewSet.as_view({"get": "report_history"})(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "شناسه دستگاه نامعتبر است.")

    def test_non_positive_device_id_is_rejected_before_queryset_access(self):
        factory = APIRequestFactory()
        request = factory.get("/api/devices/report-history/", {"device_id": "0"})
        force_authenticate(
            request,
            user=SimpleNamespace(pk=1, is_authenticated=True, is_site_admin=True),
        )

        response = DeviceViewSet.as_view({"get": "report_history"})(request)

        self.assertEqual(response.status_code, 400)




class PersonalAlertPreferencesSecurityTests(SimpleTestCase):
    def test_alert_preferences_endpoint_is_not_available_to_non_personal_roles(self):
        request = APIRequestFactory().get('/api/devices/alert-preferences/')
        force_authenticate(
            request,
            user=SimpleNamespace(
                pk=1,
                is_authenticated=True,
                is_personal_user=False,
                is_branch_manager=False,
            ),
        )

        response = DeviceViewSet.as_view({'get': 'alert_preferences'})(request)

        self.assertEqual(response.status_code, 403)
        self.assertIn('فقط برای مشتری شخصی', response.data['detail'])


class BranchManagerAlertPreferencesTests(TestCase):
    def test_branch_manager_can_read_and_update_own_alert_preferences(self):
        from rest_framework.test import APIClient

        organization = Organization.objects.create(
            name='Branch Alert Preferences Org',
            code='BR-ALERT-PREF',
        )
        branch = Branch.objects.create(
            organization=organization,
            name='Branch Alert Preferences',
            code='BR-ALERT-PREF',
        )
        manager = User.objects.create_user(
            username='branch_alert_preferences',
            password='test-password',
            role='branch_manager',
            account_type='organization',
            organization=organization,
            branch=branch,
        )
        client = APIClient()
        client.force_authenticate(user=manager)

        initial = client.get('/api/devices/alert-preferences/')
        self.assertEqual(initial.status_code, 200)
        self.assertEqual(initial.data, {'disabled_event_types': []})

        updated = client.put(
            '/api/devices/alert-preferences/',
            {'disabled_event_types': ['deviceOffline', 'deviceOverspeed']},
            format='json',
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(
            updated.data['disabled_event_types'],
            ['deviceOffline', 'deviceOverspeed'],
        )


class AlertsEndpointUnsupportedRoleTests(SimpleTestCase):
    def test_alerts_endpoint_rejects_unsupported_roles(self):
        request = APIRequestFactory().get('/api/devices/alerts/')
        force_authenticate(
            request,
            user=SimpleNamespace(
                pk=1,
                is_authenticated=True,
                is_personal_user=False,
                is_site_admin=False,
                is_main_user=False,
                is_branch_manager=False,
            ),
        )

        response = DeviceViewSet.as_view({'get': 'alerts'})(request)

        self.assertEqual(response.status_code, 403)
        self.assertIn('اجازه مشاهده هشدارها', response.data['detail'])





class OrganizationDeviceAccessQueryTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Access Test Org', code='ACCESS-TEST')
        self.branch = Branch.objects.create(organization=self.organization, name='Branch A', code='A')
        self.other_branch = Branch.objects.create(organization=self.organization, name='Branch B', code='B')
        self.main_user = User.objects.create_user(
            username='access_test_main', password='test-password',
            role='main_user', account_type='organization', organization=self.organization,
        )
        self.branch_user = User.objects.create_user(
            username='access_test_branch', password='test-password',
            role='branch_manager', account_type='organization',
            organization=self.organization, branch=self.branch,
        )
        self.now = timezone.now()

    def make_device_access(self, imei, branch, started_at):
        device = Device.objects.create(imei=imei, organization=self.organization, branch=branch, management_status='active')
        today = timezone.localdate()
        subscription = Subscription.objects.create(
            contract_number=f'ACCESS-{imei}',
            customer_type='organization',
            organization=self.organization,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=30),
            status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device, organization=self.organization, branch=branch,
            subscription=subscription, started_at=started_at,
        )
        return device



    def test_organization_and_branch_lists_exclude_future_access_periods(self):
        current_org_device = self.make_device_access(
            '860000000000201', self.branch, self.now - timedelta(days=1),
        )
        future_org_device = self.make_device_access(
            '860000000000202', self.branch, self.now + timedelta(days=1),
        )
        current_other_branch = self.make_device_access(
            '860000000000203', self.other_branch, self.now - timedelta(days=1),
        )
        future_branch_device = self.make_device_access(
            '860000000000204', self.branch, self.now + timedelta(days=2),
        )

        main_request = APIRequestFactory().get('/api/devices/')
        force_authenticate(main_request, user=self.main_user)
        main_view = DeviceViewSet()
        main_view.action_map = {'get': 'list'}
        main_view.request = main_view.initialize_request(main_request)
        main_visible = set(main_view.get_queryset().values_list('id', flat=True))
        self.assertEqual(main_visible, {
            current_org_device.id, current_other_branch.id,
        })

        branch_request = APIRequestFactory().get('/api/devices/')
        force_authenticate(branch_request, user=self.branch_user)
        branch_view = DeviceViewSet()
        branch_view.action_map = {'get': 'list'}
        branch_view.request = branch_view.initialize_request(branch_request)
        branch_visible = set(branch_view.get_queryset().values_list('id', flat=True))
        self.assertEqual(branch_visible, {current_org_device.id})


class PersonalDeviceAccessQueryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='personal_device_access',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        self.other_user = User.objects.create_user(
            username='other_personal_device_access',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        self.now = timezone.now()

    def make_device(self, imei, user, started_at, ended_at=None):
        device = Device.objects.create(
            imei=imei,
            owner_user=user,
            management_status='active',
        )
        today = timezone.localdate()
        subscription = Subscription.objects.create(
            contract_number=f'PERSONAL-{imei}',
            customer_type='personal',
            user=user,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=30),
            status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            user=user,
            subscription=subscription,
            started_at=started_at,
            ended_at=ended_at,
        )
        return device

    def test_personal_device_list_contains_only_current_access_periods(self):
        active = self.make_device(
            '860000000000101',
            self.user,
            self.now - timedelta(days=1),
        )
        ending_later = self.make_device(
            '860000000000102',
            self.user,
            self.now - timedelta(days=2),
            self.now + timedelta(days=1),
        )
        self.make_device(
            '860000000000103',
            self.user,
            self.now + timedelta(days=1),
        )
        self.make_device(
            '860000000000104',
            self.user,
            self.now - timedelta(days=2),
            self.now - timedelta(seconds=1),
        )
        self.make_device(
            '860000000000105',
            self.other_user,
            self.now - timedelta(days=1),
        )

        request = APIRequestFactory().get('/api/devices/')
        force_authenticate(request, user=self.user)
        view = DeviceViewSet()
        view.action_map = {'get': 'list'}
        view.request = view.initialize_request(request)

        visible_ids = set(view.get_queryset().values_list('id', flat=True))

        self.assertEqual(visible_ids, {active.id, ending_later.id})

    def test_personal_device_list_includes_current_active_contract_links_without_access_period(self):
        today = timezone.localdate()
        device = Device.objects.create(
            imei='860000000000106',
            management_status='installed',
        )
        subscription = Subscription.objects.create(
            contract_number='PERSONAL-ACCESS-TEST-001',
            customer_type='personal',
            user=self.user,
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=30),
            status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=30),
        )

        request = APIRequestFactory().get('/api/devices/')
        force_authenticate(request, user=self.user)
        view = DeviceViewSet()
        view.action_map = {'get': 'list'}
        view.request = view.initialize_request(request)

        visible_ids = set(view.get_queryset().values_list('id', flat=True))

        self.assertEqual(visible_ids, {device.id})
        self.assertFalse(DeviceCustomerAccessPeriod.objects.filter(device=device).exists())


    @patch('fleet.views.traccar_device_positions')
    @patch('fleet.views.traccar_device_by_unique_id')
    def test_report_history_paginates_from_last_fix_time_without_refetching_earlier_rows(
        self, lookup_device, fetch_positions
    ):
        today = timezone.localdate()
        device = Device.objects.create(
            imei='860000000000110',
            management_status='installed',
        )
        subscription = Subscription.objects.create(
            contract_number='PERSONAL-REPORT-PAGING-TEST-001',
            customer_type='personal',
            user=self.user,
            start_date=today - timedelta(days=2),
            end_date=today + timedelta(days=2),
            status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=today - timedelta(days=2),
            end_date=today + timedelta(days=2),
        )
        lookup_device.return_value = {'id': 42}

        base_time = timezone.now().replace(microsecond=0)
        first_page = [
            {
                'id': index + 1,
                'fixTime': (base_time + timedelta(seconds=index)).isoformat(),
                'serverTime': (base_time + timedelta(seconds=index)).isoformat(),
                'latitude': 91,
                'longitude': 0,
            }
            for index in range(5001)
        ]
        fetch_positions.side_effect = [
            first_page,
            first_page[4999:],
        ]

        query_start = base_time.isoformat().replace('+00:00', 'Z')
        query_end = (base_time + timedelta(hours=2)).isoformat().replace('+00:00', 'Z')
        first_request = APIRequestFactory().get(
            '/api/devices/report-history/',
            {
                'device_id': str(device.pk),
                'from': query_start,
                'to': query_end,
            },
        )
        force_authenticate(first_request, user=self.user)
        first_response = DeviceViewSet.as_view({'get': 'report_history'})(first_request)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first_response.data['next_cursor']['cursor_id'], 5000)
        self.assertEqual(fetch_positions.call_args.kwargs['limit'], 5001)

        cursor = first_response.data['next_cursor']
        second_request = APIRequestFactory().get(
            '/api/devices/report-history/',
            {
                'device_id': str(device.pk),
                'from': query_start,
                'to': query_end,
                **cursor,
            },
        )
        force_authenticate(second_request, user=self.user)
        second_response = DeviceViewSet.as_view({'get': 'report_history'})(second_request)

        self.assertEqual(second_response.status_code, 200)
        self.assertIsNone(second_response.data['next_cursor'])
        self.assertEqual(fetch_positions.call_count, 2)
        self.assertEqual(
            fetch_positions.call_args_list[1].args[1],
            cursor['cursor_fix_time'].replace('+00:00', 'Z'),
        )

    def test_personal_report_history_accepts_current_contract_link_without_access_period(self):
        today = timezone.localdate()
        device = Device.objects.create(
            imei='860000000000107',
            management_status='installed',
        )
        subscription = Subscription.objects.create(
            contract_number='PERSONAL-REPORT-TEST-001',
            customer_type='personal',
            user=self.user,
            start_date=today - timedelta(days=2),
            end_date=today + timedelta(days=20),
            status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=20),
        )

        request = APIRequestFactory().get(
            '/api/devices/report-history/',
            {'device_id': str(device.pk), 'metadata': 'true'},
        )
        force_authenticate(request, user=self.user)
        response = DeviceViewSet.as_view({'get': 'report_history'})(request)

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data['range_start'])
        self.assertIsNotNone(response.data['range_end'])
        self.assertFalse(response.data['unrestricted'])

    def test_personal_report_range_uses_contract_dates_not_narrower_access_period(self):
        today = timezone.localdate()
        contract_start = today - timedelta(days=12)
        contract_end = today + timedelta(days=18)
        device_start = today - timedelta(days=10)
        device_end = today + timedelta(days=15)
        access_start = timezone.make_aware(
            datetime.combine(today - timedelta(days=2), datetime.min.time())
        )
        access_end = timezone.make_aware(
            datetime.combine(today + timedelta(days=3), datetime.max.time())
        )
        device = Device.objects.create(
            imei='860000000000109',
            management_status='installed',
        )
        subscription = Subscription.objects.create(
            contract_number='PERSONAL-REPORT-RANGE-TEST-001',
            customer_type='personal',
            user=self.user,
            start_date=contract_start,
            end_date=contract_end,
            status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=device_start,
            end_date=device_end,
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            user=self.user,
            subscription=subscription,
            started_at=access_start,
            ended_at=access_end,
        )

        request = APIRequestFactory().get(
            '/api/devices/report-history/',
            {'device_id': str(device.pk), 'metadata': 'true'},
        )
        force_authenticate(request, user=self.user)
        response = DeviceViewSet.as_view({'get': 'report_history'})(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            parse_datetime(response.data['range_start']).date(),
            device_start,
        )
        self.assertEqual(
            parse_datetime(response.data['range_end']).date(),
            device_end,
        )

    def test_personal_report_history_rejects_access_period_without_contract_link(self):
        device = self.make_device(
            '860000000000108',
            self.user,
            self.now - timedelta(days=3),
        )
        # An open access row without a current contract-device link grants nothing.
        device.subscription_links.all().delete()

        request = APIRequestFactory().get(
            '/api/devices/report-history/',
            {'device_id': str(device.pk), 'metadata': 'true'},
        )
        force_authenticate(request, user=self.user)
        response = DeviceViewSet.as_view({'get': 'report_history'})(request)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.data['detail'],
            'گزارش این دستگاه فقط در بازه قرارداد فعال قابل مشاهده است.',
        )


class PersonalTraccarAlertsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='personal_traccar_alerts',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        self.other_user = User.objects.create_user(
            username='other_personal_traccar_alerts',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        today = timezone.localdate()
        self.device = Device.objects.create(
            imei='860000000000301',
            management_status='active',
        )
        self.subscription = Subscription.objects.create(
            contract_number='PERSONAL-ALERTS-TEST-001',
            customer_type='personal',
            user=self.user,
            start_date=today - timedelta(days=20),
            end_date=today + timedelta(days=20),
            status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=self.subscription,
            device=self.device,
            start_date=today - timedelta(days=20),
            end_date=today + timedelta(days=20),
        )
        # Keep the technical assignment boundary earlier than the event fixtures.
        SubscriptionDevice.objects.filter(
            subscription=self.subscription, device=self.device
        ).update(assigned_at=timezone.now() - timedelta(days=1))

    @patch('fleet.views.traccar_device_events')
    @patch('fleet.views.traccar_devices')
    def test_get_returns_real_traccar_events_for_contract_device(
        self, list_devices, fetch_events
    ):
        event_time = timezone.now().replace(microsecond=0)
        list_devices.return_value = [{'id': 42, 'uniqueId': self.device.imei}]
        fetch_events.return_value = [{
            'id': 701,
            'deviceId': 42,
            'type': 'deviceOffline',
            'eventTime': event_time.isoformat(),
            'attributes': {},
        }]
        request = APIRequestFactory().get('/api/devices/alerts/')
        force_authenticate(request, user=self.user)

        response = DeviceViewSet.as_view({'get': 'alerts'})(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['counts']['unread'], 1)
        self.assertEqual(response.data['results'][0]['id'], '701')
        self.assertEqual(response.data['results'][0]['status'], 'unread')
        self.assertEqual(fetch_events.call_args.args[0], [42])

    @patch('fleet.views.traccar_device_events')
    @patch('fleet.views.traccar_devices')
    def test_refresh_preserves_existing_user_workflow_state(
        self, list_devices, fetch_events
    ):
        event_time = timezone.now().replace(microsecond=0)
        read_at = event_time - timedelta(minutes=5)
        DeviceAlertState.objects.create(
            user=self.user,
            device=self.device,
            event_key=f'gps:{self.device.pk}:704',
            notification_type='gps',
            traccar_event_id='704',
            event_type='deviceOffline',
            event_time=event_time,
            status='read',
            read_at=read_at,
        )
        list_devices.return_value = [{'id': 42, 'uniqueId': self.device.imei}]
        fetch_events.return_value = [{
            'id': 704,
            'deviceId': 42,
            'type': 'deviceOffline',
            'eventTime': event_time.isoformat(),
            'attributes': {},
        }]
        request = APIRequestFactory().get('/api/devices/alerts/')
        force_authenticate(request, user=self.user)

        response = DeviceViewSet.as_view({'get': 'alerts'})(request)

        self.assertEqual(response.status_code, 200)
        state = DeviceAlertState.objects.get(
            user=self.user, device=self.device, traccar_event_id='704'
        )
        self.assertEqual(state.status, 'read')
        self.assertEqual(state.read_at, read_at)
        self.assertEqual(response.data['results'][0]['status'], 'read')

    @patch('fleet.views.traccar_device_events')
    @patch('fleet.views.traccar_devices')
    def test_online_event_resolves_previous_offline_event(
        self, list_devices, fetch_events
    ):
        offline_time = timezone.now() - timedelta(hours=2)
        online_time = timezone.now()
        list_devices.return_value = [{'id': 42, 'uniqueId': self.device.imei}]
        fetch_events.return_value = [
            {'id': 702, 'deviceId': 42, 'type': 'deviceOffline', 'eventTime': offline_time.isoformat()},
            {'id': 703, 'deviceId': 42, 'type': 'deviceOnline', 'eventTime': online_time.isoformat()},
        ]
        request = APIRequestFactory().get('/api/devices/alerts/')
        force_authenticate(request, user=self.user)

        response = DeviceViewSet.as_view({'get': 'alerts'})(request)

        offline_alert = next(
            item for item in response.data['results'] if item['id'] == '702'
        )
        self.assertEqual(offline_alert['status'], 'resolved')
        self.assertIsNotNone(offline_alert['resolved_at'])

    def test_post_cannot_change_alert_state_for_another_customers_device(self):
        today = timezone.localdate()
        other_device = Device.objects.create(
            imei='860000000000302',
            management_status='active',
        )
        other_subscription = Subscription.objects.create(
            contract_number='PERSONAL-ALERTS-TEST-002',
            customer_type='personal',
            user=self.other_user,
            start_date=today - timedelta(days=2),
            end_date=today + timedelta(days=2),
            status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=other_subscription,
            device=other_device,
            start_date=today - timedelta(days=2),
            end_date=today + timedelta(days=2),
        )
        request = APIRequestFactory().post(
            '/api/devices/alerts/',
            {'device_id': other_device.pk, 'event_id': '999', 'status': 'resolved'},
            format='json',
        )
        force_authenticate(request, user=self.user)

        response = DeviceViewSet.as_view({'post': 'alerts'})(request)

        self.assertEqual(response.status_code, 404)



    def test_bulk_mark_all_read_only_updates_alerts_for_accessible_devices(self):
        other_device = Device.objects.create(
            imei='860000000000399',
            management_status='active',
        )
        event_time = timezone.now()
        own_state = DeviceAlertState.objects.create(
            user=self.user,
            device=self.device,
            traccar_event_id='own-event',
            event_key=f'gps:{self.device.pk}:own-event',
            event_type='deviceOffline',
            event_time=event_time,
        )
        outside_state = DeviceAlertState.objects.create(
            user=self.user,
            device=other_device,
            traccar_event_id='outside-event',
            event_key=f'gps:{other_device.pk}:outside-event',
            event_type='deviceOffline',
            event_time=event_time,
        )

        request = APIRequestFactory().post(
            '/api/devices/alerts/',
            {'mark_all': True},
            format='json',
        )
        force_authenticate(request, user=self.user)
        response = DeviceViewSet.as_view({'post': 'alerts'})(request)

        self.assertEqual(response.status_code, 200)
        own_state.refresh_from_db()
        outside_state.refresh_from_db()
        self.assertEqual(own_state.status, 'read')
        self.assertEqual(outside_state.status, 'unread')


class PersonalLifecycleEventAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='personal_lifecycle_access',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        self.other_user = User.objects.create_user(
            username='other_personal_lifecycle_access',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        self.admin = User.objects.create_user(
            username='lifecycle_admin_access',
            password='test-password',
            role='site_admin',
            account_type='admin',
            is_staff=True,
            is_superuser=True,
        )
        self.today = timezone.localdate()
        self.now = timezone.now()

    def make_contract_event(self, *, user, imei, event_date=None):
        device = Device.objects.create(
            imei=imei,
            management_status='installed',
        )
        subscription = Subscription.objects.create(
            contract_number=f'PERSONAL-LIFECYCLE-{imei[-4:]}',
            customer_type='personal',
            user=user,
            start_date=self.today - timedelta(days=2),
            end_date=self.today + timedelta(days=20),
            status='active',
        )
        link = SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=self.today - timedelta(days=1),
            end_date=self.today + timedelta(days=20),
        )
        event = DeviceLifecycleEvent.objects.create(
            device=device,
            event_type='assigned_to_contract',
            event_date=event_date or timezone.now(),
            subscription=subscription,
        )
        return device, link, event

    def get_visible_event_ids(self, user):
        request = APIRequestFactory().get('/api/device-lifecycle-events/')
        force_authenticate(request, user=user)
        view = DeviceLifecycleEventViewSet()
        view.action_map = {'get': 'list'}
        view.request = view.initialize_request(request)
        return set(view.get_queryset().values_list('id', flat=True))

    def test_personal_user_cannot_see_internal_lifecycle_events(self):
        _, _, event = self.make_contract_event(
            user=self.user,
            imei='860000000000201',
        )

        self.assertFalse(
            DeviceCustomerAccessPeriod.objects.filter(device=event.device).exists()
        )
        self.assertEqual(self.get_visible_event_ids(self.user), set())

    def test_site_admin_can_see_lifecycle_events(self):
        _, _, event = self.make_contract_event(
            user=self.user,
            imei='860000000000205',
        )

        self.assertEqual(self.get_visible_event_ids(self.admin), {event.id})

    def test_personal_user_cannot_see_another_users_contract_events(self):
        self.make_contract_event(
            user=self.user,
            imei='860000000000202',
        )
        self.make_contract_event(
            user=self.other_user,
            imei='860000000000203',
        )

        self.assertEqual(self.get_visible_event_ids(self.user), set())

    def test_contract_event_is_hidden_after_device_assignment_ended(self):
        _, link, event = self.make_contract_event(
            user=self.user,
            imei='860000000000204',
        )
        link.unassigned_at = event.event_date - timedelta(minutes=1)
        link.save(update_fields=['unassigned_at'])

        self.assertEqual(self.get_visible_event_ids(self.user), set())


class LiveMapDeviceCoverageTests(SimpleTestCase):
    @patch("fleet.views.traccar_current_positions", return_value=[])
    @patch(
        "fleet.views.traccar_devices",
        return_value=[{
            "id": 17,
            "uniqueId": "352016703005868",
            "status": "online",
            "lastUpdate": "2026-11-16T18:00:00Z",
        }],
    )
    @patch(
        "fleet.views.timezone.now",
        return_value=parse_datetime("2026-11-16T18:01:00Z"),
    )
    def test_map_returns_authorized_devices_without_positions_as_unknown(
        self, _now, _traccar_devices, _positions
    ):
        first = SimpleNamespace(
            pk=1, imei="352016703005868", vehicle_id=None, vehicle=None
        )
        second = SimpleNamespace(
            pk=2, imei="352016703005869", vehicle_id=None, vehicle=None
        )
        queryset = MagicMock()
        queryset.select_related.return_value = [first, second]

        view = DeviceViewSet()
        view.get_queryset = MagicMock(return_value=queryset)
        view.filter_queryset = MagicMock(return_value=queryset)

        response = view.map_positions(SimpleNamespace())

        self.assertEqual(len(response.data), 2)
        self.assertEqual(
            [item["device_id"] for item in response.data],
            [1, 2],
        )
        self.assertEqual(
            [item["status"] for item in response.data],
            ["unknown", "unknown"],
        )
        self.assertTrue(all(item["latitude"] is None for item in response.data))
        self.assertTrue(all(item["longitude"] is None for item in response.data))
        self.assertTrue(all(item["has_position"] is False for item in response.data))


class OrganizationAndAdminAlertsAccessTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name='Alerts Access Organization',
            code='ALERTS-ACCESS-ORG',
        )
        self.branch = Branch.objects.create(
            organization=self.organization,
            name='Alerts Branch',
            code='ALERTS-BR',
        )
        self.other_branch = Branch.objects.create(
            organization=self.organization,
            name='Other Alerts Branch',
            code='ALERTS-BR-2',
        )
        self.main_user = User.objects.create_user(
            username='alerts-main-user',
            password='test-password',
            account_type='organization',
            role='main_user',
            organization=self.organization,
        )
        self.branch_user = User.objects.create_user(
            username='alerts-branch-user',
            password='test-password',
            account_type='organization',
            role='branch_manager',
            organization=self.organization,
            branch=self.branch,
        )
        self.admin = User.objects.create_user(
            username='alerts-site-admin',
            password='test-password',
            account_type='admin',
            role='site_admin',
            is_staff=True,
            is_superuser=True,
        )

    def make_access_device(self, imei, branch):
        device = Device.objects.create(
            imei=imei, organization=self.organization, branch=branch,
            management_status='active',
        )
        today = timezone.localdate()
        subscription = Subscription.objects.create(
            contract_number=f'ALERT-{imei}',
            customer_type='organization',
            organization=self.organization,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=30),
            status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=self.organization,
            branch=branch,
            subscription=subscription,
            started_at=timezone.now() - timedelta(days=2),
        )
        return device

    @patch('fleet.views.traccar_device_events')
    @patch('fleet.views.traccar_devices')
    def test_organization_user_receives_traccar_alerts_for_authorized_devices(
        self, list_devices, fetch_events
    ):
        device = self.make_access_device('860000000000801', self.branch)
        list_devices.return_value = [{'id': 8801, 'uniqueId': device.imei}]
        event_time = timezone.now().replace(microsecond=0)
        fetch_events.return_value = [{
            'id': 8802,
            'deviceId': 8801,
            'type': 'deviceOffline',
            'eventTime': event_time.isoformat(),
            'attributes': {},
        }]
        request = APIRequestFactory().get('/api/devices/alerts/')
        force_authenticate(request, user=self.main_user)

        response = DeviceViewSet.as_view({'get': 'alerts'})(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'][0]['device_id'], device.pk)
        self.assertEqual(response.data['results'][0]['status'], 'unread')

    @patch('fleet.views.traccar_device_events')
    @patch('fleet.views.traccar_devices')
    def test_branch_manager_does_not_receive_other_branch_device_alerts(
        self, list_devices, fetch_events
    ):
        self.make_access_device('860000000000802', self.other_branch)
        request = APIRequestFactory().get('/api/devices/alerts/')
        force_authenticate(request, user=self.branch_user)

        response = DeviceViewSet.as_view({'get': 'alerts'})(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'], [])
        list_devices.assert_not_called()
        fetch_events.assert_not_called()

    @patch('fleet.views.traccar_device_events')
    @patch('fleet.views.traccar_devices')
    def test_site_admin_receives_traccar_alerts_without_customer_access_period(
        self, list_devices, fetch_events
    ):
        device = Device.objects.create(
            imei='860000000000803',
            management_status='warehouse',
        )
        list_devices.return_value = [{'id': 8803, 'uniqueId': device.imei}]
        event_time = timezone.now().replace(microsecond=0)
        fetch_events.return_value = [{
            'id': 8804,
            'deviceId': 8803,
            'type': 'deviceOffline',
            'eventTime': event_time.isoformat(),
            'attributes': {},
        }]
        request = APIRequestFactory().get('/api/devices/alerts/')
        force_authenticate(request, user=self.admin)

        response = DeviceViewSet.as_view({'get': 'alerts'})(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'][0]['device_id'], device.pk)
