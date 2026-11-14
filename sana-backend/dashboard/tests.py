from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from .models import SiteSettings


class SiteSettingsAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='settings_admin',
            password='test-password',
            role='site_admin',
            account_type='admin',
        )
        self.member = User.objects.create_user(
            username='settings_member',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )

    def test_authenticated_user_can_read_default_settings(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.get('/api/site-settings/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['map_provider'], 'leaflet-osm')
        self.assertEqual(response.data['map_refresh_interval_seconds'], 10)
        self.assertTrue(SiteSettings.objects.filter(pk=1).exists())

    def test_only_site_admin_can_change_settings(self):
        self.client.force_authenticate(user=self.member)
        denied = self.client.patch(
            '/api/site-settings/',
            {'map_provider': 'neshan-leaflet'},
            format='json',
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(user=self.admin)
        allowed = self.client.patch(
            '/api/site-settings/',
            {
                'map_provider': 'neshan-leaflet',
                'map_refresh_interval_seconds': 5,
            },
            format='json',
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.data['map_provider'], 'neshan-leaflet')
        self.assertEqual(allowed.data['map_refresh_interval_seconds'], 5)

    def test_rejects_out_of_range_refresh_interval(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(
            '/api/site-settings/',
            {'map_refresh_interval_seconds': 2},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            SiteSettings.objects.get(pk=1).map_refresh_interval_seconds,
            10,
        )


class AdminDashboardOverviewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='overview_admin',
            password='test-password',
            role='site_admin',
            account_type='admin',
        )
        self.member = User.objects.create_user(
            username='overview_member',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )

    def test_admin_can_read_overview(self):
        from unittest.mock import patch

        self.client.force_authenticate(user=self.admin)
        with patch('dashboard.admin_overview._server_stats', return_value={
            'database': {'status': 'connected', 'size_bytes': 1024},
            'services': {'traccar.service': 'active'},
        }), patch('dashboard.admin_overview.traccar_devices', return_value=[
            {'status': 'online'}, {'status': 'offline'}, {'status': 'online'},
        ]):
            response = self.client.get('/api/dashboard/admin-overview/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['traccar']['registered'], 3)
        self.assertEqual(response.data['traccar']['online'], 2)
        self.assertEqual(response.data['traccar']['offline'], 1)
        self.assertEqual(response.data['server']['database']['status'], 'connected')
        self.assertIn('contracts', response.data)
        self.assertIn('customers', response.data)
        self.assertIn('fleet', response.data)

    def test_non_admin_cannot_read_overview(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.get('/api/dashboard/admin-overview/')
        self.assertEqual(response.status_code, 403)

    def test_inventory_and_active_contract_device_counts_use_current_state(self):
        from datetime import timedelta
        from unittest.mock import patch

        from django.utils import timezone

        from fleet.models import Device
        from organizations.models import Subscription, SubscriptionDevice

        today = timezone.localdate()
        warehouse_device = Device.objects.create(imei='860000000000001', management_status='warehouse')
        expired_link_device = Device.objects.create(imei='860000000000002', management_status='installed')
        subscription = Subscription.objects.create(
            contract_number='TEST-OVERVIEW-001',
            customer_type='personal',
            user=self.member,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=30),
            status='active',
        )
        SubscriptionDevice.objects.bulk_create([
            SubscriptionDevice(
                subscription=subscription,
                device=warehouse_device,
                start_date=today - timedelta(days=1),
                end_date=today + timedelta(days=10),
            ),
            SubscriptionDevice(
                subscription=subscription,
                device=expired_link_device,
                start_date=today - timedelta(days=10),
                end_date=today - timedelta(days=1),
            ),
        ])

        self.client.force_authenticate(user=self.admin)
        with patch('dashboard.admin_overview._server_stats', return_value={
            'database': {'status': 'connected', 'size_bytes': 1024},
            'services': {},
        }), patch('dashboard.admin_overview.traccar_devices', return_value=[]):
            response = self.client.get('/api/dashboard/admin-overview/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['fleet']['warehouse'], 1)
        self.assertEqual(response.data['fleet']['devices_by_management_status']['warehouse'], 1)
        self.assertEqual(response.data['contracts']['active_devices'], 1)



class PersonalDashboardDeviceAccessTests(TestCase):
    def setUp(self):
        from fleet.models import Device, DeviceCustomerAccessPeriod

        self.client = APIClient()
        self.member = User.objects.create_user(
            username='personal_dashboard_member',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        self.other_member = User.objects.create_user(
            username='personal_dashboard_other',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        self.Device = Device
        self.DeviceCustomerAccessPeriod = DeviceCustomerAccessPeriod

    def test_personal_dashboard_counts_current_access_periods_not_device_ownership(self):
        from django.utils import timezone
        from datetime import timedelta

        accessible_device = self.Device.objects.create(
            imei='860000000000101',
            management_status='active',
            owner_user=self.other_member,
        )
        self.DeviceCustomerAccessPeriod.objects.create(
            device=accessible_device,
            user=self.member,
            started_at=timezone.now() - timedelta(days=1),
        )

        owned_but_not_accessible = self.Device.objects.create(
            imei='860000000000102',
            management_status='faulty',
            owner_user=self.member,
        )
        self.DeviceCustomerAccessPeriod.objects.create(
            device=owned_but_not_accessible,
            user=self.other_member,
            started_at=timezone.now() - timedelta(days=1),
        )

        ended_device = self.Device.objects.create(
            imei='860000000000103',
            management_status='disconnected',
        )
        self.DeviceCustomerAccessPeriod.objects.create(
            device=ended_device,
            user=self.member,
            started_at=timezone.now() - timedelta(days=3),
            ended_at=timezone.now() - timedelta(days=1),
        )

        future_device = self.Device.objects.create(
            imei='860000000000104',
            management_status='installed',
        )
        self.DeviceCustomerAccessPeriod.objects.create(
            device=future_device,
            user=self.member,
            started_at=timezone.now() + timedelta(days=1),
        )

        self.client.force_authenticate(user=self.member)
        response = self.client.get('/api/dashboard/stats/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['devices'], 1)
        self.assertEqual(response.data['devices_by_status'], {'active': 1})
