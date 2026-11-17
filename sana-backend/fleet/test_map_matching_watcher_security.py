from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from fleet.views import DeviceViewSet


class MapMatchingWatcherOwnershipTests(TestCase):
    def test_existing_watcher_session_cannot_be_reassigned_to_another_user(self):
        user = User.objects.create_user(
            username='map-watcher-owner',
            password='test-password',
            account_type='personal',
            role='personal_user',
        )
        request = APIRequestFactory().post(
            '/api/devices/map-matching-activity/',
            {'session_id': 'client-supplied-session-id', 'active': True},
            format='json',
        )
        force_authenticate(request, user=user)

        cursor = MagicMock()
        cursor_context = MagicMock()
        cursor_context.__enter__.return_value = cursor
        cursor_context.__exit__.return_value = False

        with patch('fleet.views.connection.cursor', return_value=cursor_context):
            response = DeviceViewSet.as_view(
                {'post': 'map_matching_activity'}
            )(request)

        self.assertEqual(response.status_code, 200)
        sql = cursor.execute.call_args.args[0]
        self.assertIn(
            'WHERE gps.map_matching_watchers.user_id = EXCLUDED.user_id',
            sql,
        )
        self.assertNotIn('SET user_id = EXCLUDED.user_id', sql)
