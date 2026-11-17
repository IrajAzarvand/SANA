from datetime import date, datetime, timedelta, timezone as datetime_timezone
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from organizations.models import Subscription


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
