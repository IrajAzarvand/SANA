from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User, UserSession


class SessionLifecycleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='session-admin',
            password='Session-Password-123!',
            account_type='admin',
            role='site_admin',
            is_staff=True,
            is_superuser=True,
        )
        self.client = APIClient()
        response = self.client.post(
            '/api/auth/login/',
            {'username': 'session-admin', 'password': 'Session-Password-123!'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.access = response.data['access']
        self.refresh = response.data['refresh']
        self.session = UserSession.objects.get(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')

    def test_login_creates_session_with_twelve_hour_absolute_expiry(self):
        self.assertIsNotNone(AccessToken(self.access).payload.get('sid'))
        self.assertEqual(
            self.session.expires_at - self.session.created_at,
            timedelta(hours=12),
        )

    def test_idle_session_is_rejected_and_revoked(self):
        self.session.last_activity_at = timezone.now() - timedelta(minutes=31)
        self.session.save(update_fields=['last_activity_at'])

        response = self.client.get('/api/users/me/')

        self.assertEqual(response.status_code, 401)
        self.session.refresh_from_db()
        self.assertIsNotNone(self.session.revoked_at)

    def test_absolute_expiry_is_enforced(self):
        self.session.expires_at = timezone.now() - timedelta(seconds=1)
        self.session.save(update_fields=['expires_at'])

        response = self.client.get('/api/users/me/')

        self.assertEqual(response.status_code, 401)
        self.session.refresh_from_db()
        self.assertIsNotNone(self.session.revoked_at)

    def test_refresh_rotation_invalidates_previous_refresh_token(self):
        first = self.client.post(
            '/api/auth/refresh/',
            {'refresh': self.refresh},
            format='json',
        )
        self.assertEqual(first.status_code, 200, first.data)
        self.assertIn('refresh', first.data)

        replay = self.client.post(
            '/api/auth/refresh/',
            {'refresh': self.refresh},
            format='json',
        )
        self.assertEqual(replay.status_code, 401)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {first.data['access']}")
        self.assertEqual(self.client.get('/api/users/me/').status_code, 200)

    def test_password_change_revokes_all_sessions_including_current(self):
        other_session = UserSession.objects.create(
            user=self.user,
            expires_at=timezone.now() + timedelta(hours=12),
            current_refresh_jti='another-device-refresh-jti',
        )
        response = self.client.post(
            '/api/users/change_password/',
            {
                'old_password': 'Session-Password-123!',
                'new_password': 'Changed-Password-456!',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)

        self.session.refresh_from_db()
        other_session.refresh_from_db()
        self.assertIsNotNone(self.session.revoked_at)
        self.assertIsNotNone(other_session.revoked_at)
        self.assertEqual(self.client.get('/api/users/me/').status_code, 401)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Changed-Password-456!'))

    def test_logout_revokes_only_current_session(self):
        other_session = UserSession.objects.create(
            user=self.user,
            expires_at=timezone.now() + timedelta(hours=12),
            current_refresh_jti='another-device-refresh-jti',
        )
        response = self.client.post('/api/auth/logout/')
        self.assertEqual(response.status_code, 200, response.data)

        self.session.refresh_from_db()
        other_session.refresh_from_db()
        self.assertIsNotNone(self.session.revoked_at)
        self.assertIsNone(other_session.revoked_at)
        self.assertEqual(self.client.get('/api/users/me/').status_code, 401)
