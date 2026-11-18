from django.conf import settings
from django.core.cache import cache
from django.test import TestCase
from unittest.mock import patch
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from accounts.models import User


def throttle_test_rates(scope):
    # DRF copies DEFAULT_THROTTLE_RATES onto ScopedRateThrottle at import time;
    # patch that effective mapping rather than overriding Django settings later.
    rates = dict(ScopedRateThrottle.THROTTLE_RATES)
    rates[scope] = '2/min'
    return rates


class AuthEndpointThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='throttle-password-user',
            password='Current-Password-123!',
            account_type='personal',
            role='personal_user',
        )

    def tearDown(self):
        cache.clear()

    @patch.object(ScopedRateThrottle, 'THROTTLE_RATES', throttle_test_rates('auth_login'))
    def test_login_is_rate_limited_by_client_ip(self):
        for _ in range(2):
            response = self.client.post(
                '/api/auth/login/',
                {'username': 'unknown-throttle-user', 'password': 'wrong-password'},
                format='json',
            )
            self.assertNotEqual(response.status_code, 429)

        limited = self.client.post(
            '/api/auth/login/',
            {'username': 'unknown-throttle-user', 'password': 'wrong-password'},
            format='json',
        )
        self.assertEqual(limited.status_code, 429)

    @patch.object(ScopedRateThrottle, 'THROTTLE_RATES', throttle_test_rates('auth_refresh'))
    def test_refresh_endpoint_is_rate_limited(self):
        for _ in range(2):
            response = self.client.post(
                '/api/auth/refresh/',
                {'refresh': 'not-a-valid-refresh-token'},
                format='json',
            )
            self.assertNotEqual(response.status_code, 429)

        limited = self.client.post(
            '/api/auth/refresh/',
            {'refresh': 'not-a-valid-refresh-token'},
            format='json',
        )
        self.assertEqual(limited.status_code, 429)

    @patch.object(ScopedRateThrottle, 'THROTTLE_RATES', throttle_test_rates('password_change'))
    def test_password_change_is_rate_limited_per_authenticated_user(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            'old_password': 'wrong-current-password',
            'new_password': 'New-Strong-Password-456!',
        }

        for _ in range(2):
            response = self.client.post(
                '/api/users/change_password/',
                payload,
                format='json',
            )
            self.assertNotEqual(response.status_code, 429)

        limited = self.client.post(
            '/api/users/change_password/',
            payload,
            format='json',
        )
        self.assertEqual(limited.status_code, 429)
