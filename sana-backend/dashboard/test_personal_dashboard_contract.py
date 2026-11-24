from datetime import date, datetime, timedelta, timezone as datetime_timezone
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from fleet.models import Device
from dashboard.views import DashboardStatsView
from organizations.models import Subscription, SubscriptionDevice


class PersonalDashboardContractSelectionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='personal-dashboard-contract-selection',
            password='test-password',
            account_type='personal',
            role='personal_user',
        )

    def get_dashboard(self):
        self.client.force_authenticate(user=self.user)
        return self.client.get('/api/dashboard/stats/')

    def test_future_contract_is_not_shown_as_current(self):
        today = timezone.localdate()
        Subscription.objects.create(
            contract_number='DASH-FUTURE-001',
            customer_type='personal',
            user=self.user,
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=31),
            status='active',
        )

        response = self.get_dashboard()

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['current_subscription'])

    def test_expired_or_future_parent_contract_does_not_expose_device_counts(self):
        today = timezone.localdate()
        expired_device = Device.objects.create(
            imei='860000000000411',
            management_status='installed',
        )
        future_device = Device.objects.create(
            imei='860000000000412',
            management_status='installed',
        )
        expired_subscription = Subscription.objects.create(
            contract_number='DASH-EXPIRED-DEVICE-001',
            customer_type='personal',
            user=self.user,
            start_date=today - timedelta(days=30),
            end_date=today - timedelta(days=1),
            status='active',
        )
        future_subscription = Subscription.objects.create(
            contract_number='DASH-FUTURE-DEVICE-001',
            customer_type='personal',
            user=self.user,
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=30),
            status='active',
        )
        for subscription, device in (
            (expired_subscription, expired_device),
            (future_subscription, future_device),
        ):
            SubscriptionDevice.objects.create(
                subscription=subscription,
                device=device,
                start_date=today - timedelta(days=5),
                end_date=today + timedelta(days=30),
            )
        # Creating a device link recalculates the parent subscription dates.
        # Restore them afterward to model a legacy/inconsistent link accurately.
        Subscription.objects.filter(pk=expired_subscription.pk).update(
            start_date=today - timedelta(days=30),
            end_date=today - timedelta(days=1),
        )
        Subscription.objects.filter(pk=future_subscription.pk).update(
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=30),
        )

        response = self.get_dashboard()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['devices'], 0)
        self.assertEqual(response.data['gps_status']['total'], 0)


    def test_future_created_device_link_is_not_in_personal_device_status_counts(self):
        today = timezone.localdate()
        now = timezone.now()
        device = Device.objects.create(
            imei='860000000000413',
            management_status='installed',
        )
        subscription = Subscription.objects.create(
            contract_number='DASH-FUTURE-LINK-001',
            customer_type='personal',
            user=self.user,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=20),
            status='active',
        )
        link = SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=20),
        )
        SubscriptionDevice.objects.filter(pk=link.pk).update(
            assigned_at=now + timedelta(minutes=10)
        )

        counts = DashboardStatsView().get_devices_by_status(access_user=self.user)

        self.assertEqual(counts, {})

    def test_contract_ending_on_previous_tehran_day_is_not_current(self):
        tehran_today = date(2026, 11, 18)
        utc_now = datetime(2026, 11, 17, 21, 0, tzinfo=datetime_timezone.utc)
        Subscription.objects.create(
            contract_number='DASH-LOCAL-DATE-001',
            customer_type='personal',
            user=self.user,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 17),
            status='active',
        )

        with patch('dashboard.views.timezone.now', return_value=utc_now), patch(
            'dashboard.views.timezone.localdate',
            return_value=tehran_today,
        ):
            response = self.get_dashboard()

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['current_subscription'])
