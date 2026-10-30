import io

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

    def test_capture_start_is_admin_only_and_invokes_the_fixed_helper(self):
        self.client.force_authenticate(user=self.site_admin)

        class FakeProcess:
            stdout = io.StringIO("شنود آزمایشی TCP و UDP شروع شد.\\n")
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
                {"action": "capture-start", "port": 9027},
                format="json",
                HTTP_ACCEPT="text/event-stream",
            )
            output = "".join(response.streaming_content)
        self.assertEqual(response.status_code, 200)
        self.assertIn("شنود آزمایشی TCP و UDP شروع شد", output)
        command = popen.call_args.args[0]
        self.assertEqual(command[-2:], ["capture-start", "9027"])
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
            stdout = io.StringIO("RAW transport=UDP hex=010203\\n")
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
                "/api/gps-monitor/ports/capture/9027/",
                HTTP_ACCEPT="text/event-stream",
            )
            output = "".join(response.streaming_content)
        self.assertEqual(response.status_code, 200)
        self.assertIn("RAW transport=UDP", output)
        self.assertIn("capture-tail", popen.call_args.args[0])

    def test_capture_rejects_invalid_port(self):
        self.client.force_authenticate(user=self.site_admin)
        response = self.client.get(
            "/api/gps-monitor/ports/capture/80/",
            HTTP_ACCEPT="text/event-stream",
        )
        self.assertEqual(response.status_code, 400)

    def test_non_admin_cannot_manage_traccar_ports(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post(
            "/api/gps-monitor/ports/",
            {"action": "status", "port": 9026},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

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
