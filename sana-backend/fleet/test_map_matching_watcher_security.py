from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from fleet.models import Device
from organizations.models import Subscription, SubscriptionDevice
from fleet.customer_access import authorized_devices_for_user
from fleet.views import DeviceViewSet


class MapMatchingWatcherOwnershipTests(TestCase):
    def test_existing_watcher_session_cannot_be_reassigned_to_another_user(self):
        user = User.objects.create_user(
            username='map-watcher-owner',
            password='test-password',
            account_type='personal',
            role='personal_user',
        )
        today = timezone.localdate()
        device = Device.objects.create(
            imei='860000000009981',
            owner_user=user,
            current_holder_user=user,
        )
        contract = Subscription.objects.create(
            contract_number='MAP-WATCHER-PERSONAL-CONTRACT',
            customer_type='personal',
            user=user,
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=30),
            status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=contract,
            device=device,
            start_date=contract.start_date,
            end_date=contract.end_date,
        )
        request = APIRequestFactory().post(
            '/api/devices/map-matching-activity/',
            {'session_id': 'client-supplied-session-id', 'active': True},
            format='json',
        )
        force_authenticate(request, user=user)

        cursor = MagicMock()
        cursor.rowcount = 0
        cursor_context = MagicMock()
        cursor_context.__enter__.return_value = cursor
        cursor_context.__exit__.return_value = False

        with patch('fleet.views.connection.cursor', return_value=cursor_context):
            response = DeviceViewSet.as_view(
                {'post': 'map_matching_activity'}
            )(request)

        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.data['active'])
        sql = cursor.execute.call_args.args[0]
        self.assertIn(
            'WHERE watcher.user_id = EXCLUDED.user_id',
            sql,
        )
        self.assertNotIn('SET user_id = EXCLUDED.user_id', sql)


class MapMatchingWatcherAccessTests(TestCase):
    def test_user_without_authorized_devices_cannot_start_global_matching(self):
        user = User.objects.create_user(
            username='map-watcher-no-device',
            password='test-password',
            account_type='personal',
            role='personal_user',
        )
        self.assertFalse(authorized_devices_for_user(user).exists())
        request = APIRequestFactory().post(
            '/api/devices/map-matching-activity/',
            {'session_id': 'no-device-session', 'active': True},
            format='json',
        )
        force_authenticate(request, user=user)

        with (
            patch('fleet.views.authorized_devices_for_user', return_value=Device.objects.none) as authorized_scope,
            patch('fleet.views.connection.cursor') as cursor,
        ):
            response = DeviceViewSet.as_view(
                {'post': 'map_matching_activity'}
            )(request)

        self.assertEqual(response.status_code, 403)
        authorized_scope.assert_called_once()
        self.assertEqual(authorized_scope.call_args.args[0].pk, user.pk)
        cursor.assert_not_called()

    def test_user_can_stop_own_watcher_after_access_has_been_revoked(self):
        user = User.objects.create_user(
            username='map-watcher-stop-revoked',
            password='test-password',
            account_type='personal',
            role='personal_user',
        )
        request = APIRequestFactory().post(
            '/api/devices/map-matching-activity/',
            {'session_id': 'revoked-session', 'active': False},
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
        self.assertIn('DELETE FROM gps.map_matching_watchers', cursor.execute.call_args.args[0])
