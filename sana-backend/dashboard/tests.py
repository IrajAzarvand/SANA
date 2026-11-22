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


class PersonalDashboardGPSStatusTests(TestCase):
    def setUp(self):
        from datetime import timedelta

        from django.utils import timezone
        from fleet.models import Device, DeviceCustomerAccessPeriod

        self.client = APIClient()
        self.user = User.objects.create_user(
            username='personal_dashboard_gps',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        self.other_user = User.objects.create_user(
            username='other_dashboard_gps',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        self.now = timezone.now()
        self.Device = Device
        self.DeviceCustomerAccessPeriod = DeviceCustomerAccessPeriod
        self.timedelta = timedelta

    def make_accessible_device(self, imei, *, user=None, management_status='installed'):
        device = self.Device.objects.create(
            imei=imei,
            management_status=management_status,
        )
        self.DeviceCustomerAccessPeriod.objects.create(
            device=device,
            user=user or self.user,
            started_at=self.now - self.timedelta(days=1),
        )
        return device

    def test_personal_stats_separate_live_gps_from_management_status(self):
        from unittest.mock import patch

        moving = self.make_accessible_device('860000000000301', management_status='installed')
        stopped = self.make_accessible_device('860000000000302', management_status='faulty')
        stale = self.make_accessible_device('860000000000303', management_status='installed')
        no_position = self.make_accessible_device('860000000000304', management_status='warehouse')
        other = self.make_accessible_device(
            '860000000000305',
            user=self.other_user,
            management_status='active',
        )

        traccar_devices_data = [
            {'id': 301, 'uniqueId': moving.imei, 'status': 'online'},
            {'id': 302, 'uniqueId': stopped.imei, 'status': 'online'},
            {'id': 303, 'uniqueId': stale.imei, 'status': 'online'},
            {'id': 304, 'uniqueId': no_position.imei, 'status': 'online'},
            {'id': 305, 'uniqueId': other.imei, 'status': 'online'},
        ]
        positions_data = [
            {
                'deviceId': 301,
                'serverTime': self.now.isoformat(),
                'speed': 5,
                'attributes': {'motion': False},
            },
            {
                'deviceId': 302,
                'serverTime': self.now.isoformat(),
                'speed': 0,
                'attributes': {'motion': False},
            },
            {
                'deviceId': 303,
                'serverTime': (self.now - self.timedelta(minutes=6)).isoformat(),
                'speed': 0,
                'attributes': {'motion': False},
            },
            {
                'deviceId': 305,
                'serverTime': self.now.isoformat(),
                'speed': 10,
                'attributes': {'motion': True},
            },
        ]

        self.client.force_authenticate(user=self.user)
        with patch('dashboard.views.traccar_devices', return_value=traccar_devices_data), patch(
            'dashboard.views.traccar_current_positions',
            return_value=positions_data,
        ):
            response = self.client.get('/api/dashboard/stats/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['devices'], 4)
        self.assertEqual(response.data['gps_status'], {
            'available': True,
            'total': 4,
            'online': 2,
            'offline': 2,
            'moving': 1,
            'stopped': 1,
        })
        self.assertNotIn('devices_by_management_status', response.data)
        self.assertNotIn('devices_by_status', response.data)

    def test_personal_stats_report_gps_unavailable_without_marking_devices_offline(self):
        from unittest.mock import patch

        from fleet.traccar_api import TraccarAPIError

        self.make_accessible_device('860000000000306')
        self.client.force_authenticate(user=self.user)

        with patch('dashboard.views.traccar_devices', side_effect=TraccarAPIError('unavailable')):
            response = self.client.get('/api/dashboard/stats/')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['gps_status']['available'])
        self.assertEqual(response.data['gps_status']['total'], 1)
        self.assertIsNone(response.data['gps_status']['online'])
        self.assertIsNone(response.data['gps_status']['offline'])



class MainUserDashboardSubscriptionTests(TestCase):
    def test_main_user_sees_current_active_organization_subscription(self):
        from datetime import timedelta

        from django.utils import timezone
        from organizations.models import Organization, Subscription

        organization = Organization.objects.create(
            name='Main Dashboard Org',
            code='MAIN-DASH-ORG',
        )
        manager = User.objects.create_user(
            username='main_dashboard_manager',
            password='test-password',
            role='main_user',
            account_type='organization',
            organization=organization,
        )
        today = timezone.localdate()
        subscription = Subscription.objects.create(
            contract_number='ORG-DASH-CURRENT-001',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=20),
            status='active',
        )

        self.client = APIClient()
        self.client.force_authenticate(user=manager)
        response = self.client.get('/api/dashboard/stats/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['current_subscription'], {
            'contract_number': subscription.contract_number,
            'end_date': subscription.end_date,
            'days_until_expiry': subscription.days_until_expiry,
            'is_expiring_soon': subscription.is_expiring_soon,
        })



class BranchManagerDashboardAccessTests(TestCase):
    def setUp(self):
        from django.utils import timezone
        from accounts.models import User
        from fleet.models import Device, DeviceCustomerAccessPeriod
        from organizations.models import Organization, Branch

        self.client = APIClient()
        self.organization = Organization.objects.create(
            name='Branch Dashboard Org',
            code='BR-DASH-ORG',
        )
        self.branch = Branch.objects.create(
            organization=self.organization,
            name='Branch Dashboard Branch',
            code='BR-DASH',
        )
        self.manager = User.objects.create_user(
            username='branch_dashboard_manager',
            password='test-password',
            role='branch_manager',
            account_type='organization',
            organization=self.organization,
            branch=self.branch,
        )
        self.now = timezone.now()
        self.Device = Device
        self.DeviceCustomerAccessPeriod = DeviceCustomerAccessPeriod

    def test_dashboard_counts_only_devices_with_current_branch_access(self):
        from datetime import timedelta
        from unittest.mock import patch

        active = self.Device.objects.create(
            imei='860000000000901',
            organization=self.organization,
            branch=self.branch,
        )
        ended = self.Device.objects.create(
            imei='860000000000902',
            organization=self.organization,
            branch=self.branch,
        )
        self.DeviceCustomerAccessPeriod.objects.create(
            device=active,
            organization=self.organization,
            branch=self.branch,
            started_at=self.now - timedelta(days=1),
        )
        self.DeviceCustomerAccessPeriod.objects.create(
            device=ended,
            organization=self.organization,
            branch=self.branch,
            started_at=self.now - timedelta(days=3),
            ended_at=self.now - timedelta(days=1),
        )

        self.client.force_authenticate(user=self.manager)
        with patch('dashboard.views.traccar_devices', return_value=[
            {'id': 901, 'uniqueId': active.imei, 'status': 'online'},
        ]), patch('dashboard.views.traccar_current_positions', return_value=[]):
            response = self.client.get('/api/dashboard/stats/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['devices'], 1)
        self.assertEqual(response.data['gps_status']['total'], 1)
        self.assertIsNone(response.data['current_subscription'])


class BranchManagerDashboardTenantScopeTests(TestCase):
    def test_dashboard_counts_only_vehicles_and_drivers_from_branch_organization(self):
        from unittest.mock import patch
        from accounts.models import User
        from fleet.models import Driver, Vehicle
        from organizations.models import Branch, Organization

        organization = Organization.objects.create(
            name='Dashboard Branch Tenant',
            code='DASH-BR-OWN',
        )
        other_organization = Organization.objects.create(
            name='Dashboard Foreign Tenant',
            code='DASH-BR-OTHER',
        )
        branch = Branch.objects.create(
            organization=organization,
            name='Dashboard Scoped Branch',
            code='DASH-BR',
        )
        manager = User.objects.create_user(
            username='dashboard_branch_tenant',
            password='test-password',
            role='branch_manager',
            account_type='organization',
            organization=organization,
            branch=branch,
        )
        Vehicle.objects.create(
            plate='66ج666',
            organization=organization,
            branch=branch,
        )
        Vehicle.objects.create(
            plate='77د777',
            organization=other_organization,
            branch=branch,
        )
        Driver.objects.create(
            first_name='Own',
            last_name='Driver',
            mobile='09120000003',
            organization=organization,
            branch=branch,
        )
        Driver.objects.create(
            first_name='Foreign',
            last_name='Driver',
            mobile='09120000004',
            organization=other_organization,
            branch=branch,
        )

        self.client = APIClient()
        self.client.force_authenticate(user=manager)
        with patch('dashboard.views.traccar_devices', return_value=[]), patch(
            'dashboard.views.traccar_current_positions',
            return_value=[],
        ):
            response = self.client.get('/api/dashboard/stats/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['vehicles'], 1)
        self.assertEqual(response.data['drivers'], 1)
        self.assertEqual(response.data['vehicles_by_status'], {
            'with_device': 0,
            'without_device': 1,
        })
