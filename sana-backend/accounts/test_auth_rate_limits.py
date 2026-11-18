from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import User


def throttle_test_settings(scope):
    rest_framework = dict(settings.REST_FRAMEWORK)
    rates = dict(rest_framework.get('DEFAULT_THROTTLE_RATES', {}))
    rates[scope] = '2/min'
    rest_framework['DEFAULT_THROTTLE_RATES'] = rates
    return rest_framework


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

    @override_settings(REST_FRAMEWORK=throttle_test_settings('auth_login'))
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

    @override_settings(REST_FRAMEWORK=throttle_test_settings('auth_refresh'))
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

    @override_settings(REST_FRAMEWORK=throttle_test_settings('password_change'))
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
