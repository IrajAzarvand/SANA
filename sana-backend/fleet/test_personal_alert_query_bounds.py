from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from fleet.views import DeviceViewSet


class PersonalAlertQueryBoundsTests(TestCase):
    def test_alert_endpoint_rejects_ranges_longer_than_ninety_days(self):
        user = User.objects.create_user(
            username='personal-alert-range-bound',
            password='test-password',
            account_type='personal',
            role='personal_user',
        )
        now = timezone.now()
        request = APIRequestFactory().get(
            '/api/devices/alerts/',
            {
                'from': (now - timedelta(days=91)).isoformat(),
                'to': now.isoformat(),
            },
        )
        force_authenticate(request, user=user)

        response = DeviceViewSet.as_view({'get': 'alerts'})(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn('۹۰ روز', response.data['detail'])
