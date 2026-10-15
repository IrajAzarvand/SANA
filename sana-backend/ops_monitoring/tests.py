from django.contrib.auth import get_user_model
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

    def test_anonymous_user_cannot_access_live_logs(self):
        response = self.client.get("/api/gps-monitor/logs/service/")
        self.assertIn(response.status_code, (401, 403))

    def test_non_admin_cannot_access_live_logs_or_queue(self):
        self.client.force_authenticate(user=self.regular_user)
        self.assertEqual(self.client.get("/api/gps-monitor/logs/service/").status_code, 403)
        self.assertEqual(self.client.get("/api/gps-monitor/queue/").status_code, 403)
