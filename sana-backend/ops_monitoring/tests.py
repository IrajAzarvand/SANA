import io
from unittest.mock import MagicMock, patch
from django.contrib.auth import get_user_model

from django.test import TestCase
from rest_framework.test import APIClient

from ops_monitoring.views import LIVE_CAPTURE_HELPER, STREAM_COMMANDS, _validated_capture


def stream_response_text(response):
    """Decode Django StreamingHttpResponse chunks for readable assertions."""
    chunks = []
    for chunk in response.streaming_content:
        chunks.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk)
    return "".join(chunks)


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

    def test_anonymous_user_cannot_access_multiplexed_live_logs(self):
        response = self.client.get("/api/gps-monitor/logs/")
        self.assertIn(response.status_code, (401, 403))

    def test_non_admin_cannot_access_multiplexed_live_logs(self):
        self.client.force_authenticate(user=self.regular_user)
        self.assertEqual(self.client.get("/api/gps-monitor/logs/").status_code, 403)

    def test_fixed_live_sources_are_all_configured(self):
        self.assertEqual(
            set(STREAM_COMMANDS),
            {"gps", "traccar", "backend", "postgres", "system"},
        )
        self.assertIn("--unit=traccar.service", STREAM_COMMANDS["traccar"])
        self.assertIn("--unit=sana-backend.service", STREAM_COMMANDS["backend"])

    def test_network_capture_uses_a_dedicated_validating_helper(self):
        self.assertEqual(
            LIVE_CAPTURE_HELPER,
            "/usr/local/sbin/sana-traccar-live-capture",
        )

    def test_capture_port_and_protocol_are_validated(self):
        self.assertEqual(_validated_capture("5027", "tcp"), (5027, "tcp"))
        self.assertEqual(_validated_capture("5027", "both"), (5027, "both"))
        for port, protocol in (("0", "tcp"), ("80", "tcp"), ("65536", "udp"), ("bad", "tcp"), ("5027", "icmp")):
            with self.subTest(port=port, protocol=protocol):
                with self.assertRaises(ValueError):
                    _validated_capture(port, protocol)

    def test_invalid_capture_query_is_rejected(self):
        self.client.force_authenticate(user=self.site_admin)
        response = self.client.get(
            "/api/gps-monitor/logs/?capture_port=5027&capture_protocol=icmp",
            HTTP_ACCEPT="text/event-stream",
        )
        self.assertEqual(response.status_code, 400)

    def test_live_logs_accept_server_sent_events_without_406(self):
        self.client.force_authenticate(user=self.site_admin)
        response = self.client.get(
            "/api/gps-monitor/logs/",
            HTTP_ACCEPT="text/event-stream",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")

    def test_live_logs_accept_on_demand_network_capture_parameters(self):
        self.client.force_authenticate(user=self.site_admin)
        response = self.client.get(
            "/api/gps-monitor/logs/?capture_port=5027&capture_protocol=tcp",
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
            output = stream_response_text(response)
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
            output = stream_response_text(response)
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
            output = stream_response_text(response)
        self.assertIn("sudo", output)


class TraccarRawCapturePermissionsTests(GPSMonitoringPermissionsTests):

    def test_capture_toggle_is_admin_only_and_invokes_the_fixed_helper(self):
        self.client.force_authenticate(user=self.site_admin)

        class FakeProcess:
            stdout = io.StringIO("شنود آزمایشی TCP و UDP شروع شد.\n")
            def wait(self, timeout=None):
                return 0
            def poll(self):
                return 0
            def terminate(self):
                pass
            def kill(self):
                pass

        with patch("ops_monitoring.views.shutil.which", return_value="/usr/bin/sudo"), patch(
            "ops_monitoring.views.subprocess.Popen", return_value=FakeProcess()
        ) as popen:
            response = self.client.post(
                "/api/gps-monitor/ports/",
                {"action": "capture-toggle", "port": 5015},
                format="json",
                HTTP_ACCEPT="text/event-stream",
            )
            output = stream_response_text(response)
        self.assertEqual(response.status_code, 200)
        self.assertIn("شنود آزمایشی TCP و UDP شروع شد", output)
        command = popen.call_args.args[0]
        self.assertEqual(command[-2:], ["capture-toggle", "1256"])
        self.assertIn("/usr/local/sbin/sana-traccar-port-manager", command)

    def test_capture_log_stream_is_admin_only(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(
            "/api/gps-monitor/ports/capture/9027/",
            HTTP_ACCEPT="text/event-stream",
        )
        self.assertEqual(response.status_code, 403)

    def test_capture_log_streams_from_the_fixed_helper(self):
        self.client.force_authenticate(user=self.site_admin)

        class FakeProcess:
            stdout = io.StringIO("RAW transport=UDP hex=010203\n")
            def poll(self):
                return 0
            def terminate(self):
                pass
            def wait(self, timeout=None):
                return 0
            def kill(self):
                pass

        with patch("ops_monitoring.views.shutil.which", return_value="/usr/bin/sudo"), patch(
            "ops_monitoring.views.subprocess.Popen", return_value=FakeProcess()
        ) as popen:
            response = self.client.get(
                "/api/gps-monitor/ports/capture/1256/",
                HTTP_ACCEPT="text/event-stream",
            )
            output = stream_response_text(response)
        self.assertEqual(response.status_code, 200)
        self.assertIn("RAW transport=UDP", output)
        self.assertIn("capture-tail", popen.call_args.args[0])

    def test_capture_log_stream_rejects_non_dedicated_port(self):
        self.client.force_authenticate(user=self.site_admin)
        response = self.client.get(
            "/api/gps-monitor/ports/capture/5015/",
            HTTP_ACCEPT="text/event-stream",
        )
        self.assertEqual(response.status_code, 400)

    def test_capture_rejects_invalid_port(self):
        self.client.force_authenticate(user=self.site_admin)
        response = self.client.get(
            "/api/gps-monitor/ports/capture/80/",
            HTTP_ACCEPT="text/event-stream",
        )
        self.assertEqual(response.status_code, 400)

    @patch("ops_monitoring.views.subprocess.Popen")
    @patch("ops_monitoring.views.shutil.which", return_value="/usr/bin/sudo")
    def test_capture_log_uses_fixed_tail_command(
        self,
        mock_which,
        mock_popen,
    ):
        from unittest.mock import MagicMock

        fake_process = MagicMock()
        fake_process.stdout = [
            "TCP CONNECT remote=127.0.0.1:12345\n",
            "RAW transport=TCP length=30\n",
        ]
        fake_process.poll.return_value = 0

        mock_popen.return_value = fake_process

        self.client.force_authenticate(user=self.site_admin)
        response = self.client.get(
            "/api/gps-monitor/ports/capture/1256/",
            HTTP_ACCEPT="text/event-stream",
        )

        self.assertEqual(response.status_code, 200)

        content = b"".join(response.streaming_content).decode("utf-8")

        self.assertIn("TCP CONNECT", content)
        self.assertIn("RAW transport=TCP", content)

        command = mock_popen.call_args.args[0]

        self.assertEqual(
            command,
            [
                "/usr/bin/sudo",
                "-n",
                "/usr/local/sbin/sana-traccar-port-manager",
                "capture-tail",
                "1256",
            ],
        )