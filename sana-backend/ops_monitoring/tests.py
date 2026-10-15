from django.contrib.auth import get_user_model
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient


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
