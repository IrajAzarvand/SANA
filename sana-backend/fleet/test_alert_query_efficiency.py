import re
from datetime import timedelta
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from fleet.models import Device, DeviceCustomerAccessPeriod
from fleet.views import DeviceViewSet
from organizations.models import Organization, Subscription, SubscriptionDevice


class OrganizationAlertsQueryEfficiencyTests(TestCase):
    def test_active_subscription_links_are_loaded_in_one_query_for_many_devices(self):
        organization = Organization.objects.create(
            name='Alerts Query Efficiency Organization',
            code='ALERTS-QUERY-EFFICIENCY',
        )
        manager = User.objects.create_user(
            username='alerts_query_efficiency_manager',
            password='test-password',
            role='main_user',
            account_type='organization',
            organization=organization,
        )
        now = timezone.now()
        today = timezone.localdate(now)
        traccar_devices = []

        for index in range(4):
            device = Device.objects.create(
                imei=f'8600000000089{index:03d}',
                organization=organization,
                current_holder_organization=organization,
                management_status='installed',
            )
            contract = Subscription.objects.create(
                contract_number=f'ALERTS-QUERY-CONTRACT-{index}',
                customer_type='organization',
                organization=organization,
                start_date=today - timedelta(days=5),
                end_date=today + timedelta(days=30),
                status='active',
            )
            link = SubscriptionDevice.objects.create(
                subscription=contract,
                device=device,
                start_date=contract.start_date,
                end_date=contract.end_date,
            )
            SubscriptionDevice.objects.filter(pk=link.pk).update(
                assigned_at=now - timedelta(minutes=5),
            )
            DeviceCustomerAccessPeriod.objects.create(
                device=device,
                organization=organization,
                subscription=contract,
                started_at=now - timedelta(minutes=5),
            )
            traccar_devices.append({
                'id': index + 1,
                'uniqueId': device.imei,
            })

        request = APIRequestFactory().get('/api/devices/alerts/')
        force_authenticate(request, user=manager)

        with (
            patch('fleet.views.traccar_devices', return_value=traccar_devices),
            patch('fleet.views.traccar_device_events', return_value=[]),
            CaptureQueriesContext(connection) as captured,
        ):
            response = DeviceViewSet.as_view({'get': 'alerts'})(request)

        self.assertEqual(response.status_code, 200, response.data)
        top_level_link_queries = []
        for query in captured.captured_queries:
            match = re.search(
                r'\\bFROM\\s+"?([A-Za-z0-9_]+)"?',
                query['sql'],
                re.IGNORECASE,
            )
            if match and match.group(1) == 'organizations_subscriptiondevice':
                top_level_link_queries.append(query['sql'])

        self.assertEqual(
            len(top_level_link_queries),
            1,
            'Alert access must load current subscription-device links in one batched query.',
        )
