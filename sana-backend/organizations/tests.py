from django.test import TestCase
from unittest.mock import patch

from accounts.models import User
from .serializers import SubscriptionWizardSerializer


class SubscriptionWizardExistingUserTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='existing-person',
            password='Original-Password-123',
            first_name='نام قبلی',
            last_name='نام خانوادگی قبلی',
            mobile='09120000000',
            account_type='personal',
            role='personal_user',
        )

    def _payload(self, **overrides):
        payload = {
            'customer_type': 'personal',
            'existing_user_id': self.user.id,
            'username': self.user.username,
            'first_name': 'نام جدید',
            'last_name': 'نام خانوادگی جدید',
            'mobile': '09121111111',
            'national_id': '0012345678',
            'address': 'نشانی جدید',
            'contract_number': 'PRS-TEST-0001',
            'start_date': '2026-11-07',
            'end_date': '2027-11-07',
            'devices': [],
            'payments': [],
        }
        payload.update(overrides)
        return payload

    @patch('organizations.serializers.record_device_lifecycle_event')
    def test_existing_user_is_updated_without_changing_password(self, _record_event):
        serializer = SubscriptionWizardSerializer(data=self._payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'نام جدید')
        self.assertEqual(self.user.last_name, 'نام خانوادگی جدید')
        self.assertEqual(self.user.mobile, '09121111111')
        self.assertEqual(self.user.national_id, '0012345678')
        self.assertEqual(self.user.address, 'نشانی جدید')
        self.assertTrue(self.user.check_password('Original-Password-123'))

    def test_existing_user_username_must_match_selected_account(self):
        serializer = SubscriptionWizardSerializer(
            data=self._payload(username='another-username')
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('username', serializer.errors)

    def test_new_user_requires_password(self):
        payload = self._payload()
        payload.pop('existing_user_id')
        payload['username'] = 'new-person'
        payload['contract_number'] = 'PRS-TEST-0002'
        serializer = SubscriptionWizardSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)
