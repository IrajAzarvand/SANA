from django.contrib.auth import get_user_model
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from ops_monitoring.views import STREAM_COMMANDS


class GPSMonitoringPermissionsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.regular_user = User.objects.create_user(
            username="monitoring-test-user",
            password="test-password-strong",
            role="personal_user",
            account_type="personal",
        )
        self.site_admin = User.objects.create_user(
            username="monitoring-test-admin",
            password="test-password-strong",
            role="site_admin",
            account_type="admin",
            is_staff=True,
            is_superuser=True,
        )

    def test_anonymous_user_cannot_access_live_logs(self):
        response = self.client.get("/api/gps-monitor/logs/service/")
        self.assertIn(response.status_code, (401, 403))

    def test_non_admin_cannot_access_live_logs_or_queue(self):
        self.client.force_authenticate(user=self.regular_user)
        self.assertEqual(self.client.get("/api/gps-monitor/logs/service/").status_code, 403)
        self.assertEqual(self.client.get("/api/gps-monitor/queue/").status_code, 403)

    def test_network_capture_uses_only_the_privileged_fixed_wrapper(self):
        self.assertEqual(
            STREAM_COMMANDS["network"],
            ["sudo", "-n", "/usr/local/sbin/sana-gps-network-capture"],
        )

    def test_live_logs_accept_server_sent_events_without_406(self):
        self.client.force_authenticate(user=self.site_admin)
        with patch("ops_monitoring.views.shutil.which", return_value=None):
            for stream_name in ("service", "network"):
                with self.subTest(stream_name=stream_name):
                    response = self.client.get(
                        f"/api/gps-monitor/logs/{stream_name}/",
                        HTTP_ACCEPT="text/event-stream",
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response["Content-Type"], "text/event-stream")


class TraccarPortManagementPermissionsTests(GPSMonitoringPermissionsTests):

    def test_traccar_api_test_reports_device_and_position_counts(self):
        self.client.force_authenticate(user=self.site_admin)
        with patch("ops_monitoring.views.traccar_devices", return_value=[{"id": 1}, {"id": 2}]), patch(
            "ops_monitoring.views.traccar_current_positions", return_value=[{"deviceId": 1}]
        ), patch("ops_monitoring.views.subprocess.Popen") as popen:
            response = self.client.post(
                "/api/gps-monitor/ports/",
                {"action": "api-test"},
                format="json",
                HTTP_ACCEPT="text/event-stream",
            )
            self.assertEqual(response.status_code, 200)
            output = "".join(response.streaming_content)
        self.assertIn("اتصال API ترکار و احراز هویت موفق است.", output)
        self.assertIn("دستگاه‌های ثبت‌شده در Traccar: 2", output)
        self.assertIn("موقعیت‌های فعلی برگشتی از API: 1", output)
        popen.assert_not_called()

    def test_traccar_api_test_reports_connection_failure(self):
        from fleet.traccar_api import TraccarAPIError

        self.client.force_authenticate(user=self.site_admin)
        with patch(
            "ops_monitoring.views.traccar_devices",
            side_effect=TraccarAPIError("Traccar API request failed: URLError"),
        ):
            response = self.client.post(
                "/api/gps-monitor/ports/",
                {"action": "api-test"},
                format="json",
                HTTP_ACCEPT="text/event-stream",
            )
            output = "".join(response.streaming_content)
        self.assertIn("آزمون API ناموفق بود", output)

    def test_non_admin_cannot_manage_traccar_ports(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post(
            "/api/gps-monitor/ports/",
            {"action": "status", "port": 9026},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        api_response = self.client.post(
            "/api/gps-monitor/ports/",
            {"action": "api-test"},
            format="json",
        )
        self.assertEqual(api_response.status_code, 403)

    def test_invalid_port_is_rejected_before_privileged_helper(self):
        self.client.force_authenticate(user=self.site_admin)
        with patch("ops_monitoring.views.subprocess.Popen") as popen:
            response = self.client.post(
                "/api/gps-monitor/ports/",
                {"action": "status", "port": 80},
                format="json",
            )
        self.assertEqual(response.status_code, 400)
        popen.assert_not_called()

    def test_apply_requires_verified_device_model_selection_not_protocol_input(self):
        self.client.force_authenticate(user=self.site_admin)
        response = self.client.post(
            "/api/gps-monitor/ports/",
            {"action": "apply", "port": 9026},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("مدل دستگاه", response.json()["detail"])

    def test_unknown_operation_is_rejected(self):
        self.client.force_authenticate(user=self.site_admin)
        response = self.client.post(
            "/api/gps-monitor/ports/",
            {"action": "run-shell", "port": 9026},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_port_operation_streams_a_clear_message_when_helper_is_not_installed(self):
        self.client.force_authenticate(user=self.site_admin)
        with patch("ops_monitoring.views.shutil.which", return_value=None):
            response = self.client.post(
                "/api/gps-monitor/ports/",
                {"action": "status", "port": 9026},
                format="json",
                HTTP_ACCEPT="text/event-stream",
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "text/event-stream")
            output = "".join(response.streaming_content)
        self.assertIn("sudo", output)
