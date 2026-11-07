from django.test import TestCase
from unittest.mock import patch

from accounts.models import User
from fleet.models import Device
from organizations.models import Organization, Subscription, SubscriptionDevice
from .serializers import SubscriptionWizardSerializer


class SubscriptionWizardExistingUserTests(TestCase):
    def setUp(self):
        self.lifecycle_patcher = patch('organizations.serializers.record_device_lifecycle_event')
        self.lifecycle_patcher.start()
        self.addCleanup(self.lifecycle_patcher.stop)
        self.device = Device.objects.create(imei='111111111111111')
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
            'devices': [{
                'device_id': self.device.id,
                'start_date': '2026-11-07',
                'end_date': '2027-11-07',
            }],
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


class SubscriptionWizardOrganizationSelectionTests(TestCase):
    def setUp(self):
        self.lifecycle_patcher = patch('organizations.serializers.record_device_lifecycle_event')
        self.lifecycle_patcher.start()
        self.addCleanup(self.lifecycle_patcher.stop)
        self.device = Device.objects.create(imei='222222222222222')

        self.organization = Organization.objects.create(
            name='سازمان اولیه',
            code='ORG-EXISTING-01',
            phone='02111111111',
        )
        self.manager = User.objects.create_user(
            username='existing-manager',
            password='Original-Password-123',
            first_name='مدیر',
            last_name='شرکت',
            mobile='09120000001',
            account_type='organization',
            role='main_user',
            organization=self.organization,
        )

    def _payload(self, **overrides):
        payload = {
            'customer_type': 'organization',
            'organization_id': self.organization.id,
            'organization_name': 'نام ویرایش‌شده سازمان',
            'organization_code': self.organization.code,
            'registration_number': '12345',
            'economy_code': '98765',
            'organization_phone': '02122222222',
            'organization_email': 'office@example.com',
            'organization_address': 'نشانی جدید سازمان',
            'existing_user_id': self.manager.id,
            'username': self.manager.username,
            'first_name': 'مدیر',
            'last_name': 'جدید',
            'mobile': '09121111111',
            'national_id': '',
            'address': '',
            'contract_number': 'ORG-TEST-0001',
            'start_date': '2026-11-07',
            'end_date': '2027-11-07',
            'devices': [{
                'device_id': self.device.id,
                'start_date': '2026-11-07',
                'end_date': '2027-11-07',
            }],
            'payments': [],
        }
        payload.update(overrides)
        return payload

    def test_existing_organization_is_reused_and_updated(self):
        serializer = SubscriptionWizardSerializer(data=self._payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        subscription = serializer.save()

        self.organization.refresh_from_db()
        self.manager.refresh_from_db()
        self.assertEqual(subscription.organization_id, self.organization.id)
        self.assertEqual(self.organization.name, 'نام ویرایش‌شده سازمان')
        self.assertEqual(self.organization.registration_number, '12345')
        self.assertEqual(self.organization.phone, '02122222222')
        self.assertEqual(self.manager.organization_id, self.organization.id)
        self.assertTrue(self.manager.check_password('Original-Password-123'))

    def test_existing_organization_requires_a_non_empty_name(self):
        serializer = SubscriptionWizardSerializer(
            data=self._payload(organization_name='   ')
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('organization_name', serializer.errors)

    def test_new_manager_is_attached_to_selected_existing_organization(self):
        payload = self._payload(
            existing_user_id=None,
            username='new-manager',
            password='New-Password-123',
            contract_number='ORG-TEST-0002',
        )
        serializer = SubscriptionWizardSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        subscription = serializer.save()

        self.assertEqual(subscription.organization_id, self.organization.id)
        manager = User.objects.get(username='new-manager')
        self.assertEqual(manager.organization_id, self.organization.id)
        self.assertEqual(manager.role, 'main_user')

    def test_manager_from_another_organization_is_rejected(self):
        from organizations.models import Organization

        other_organization = Organization.objects.create(
            name='سازمان دوم',
            code='ORG-EXISTING-02',
        )
        self.manager.organization = other_organization
        self.manager.save(update_fields=['organization'])

        serializer = SubscriptionWizardSerializer(data=self._payload())
        self.assertFalse(serializer.is_valid())
        self.assertIn('existing_user_id', serializer.errors)

    def test_existing_manager_cannot_be_silently_moved_to_new_organization(self):
        payload = self._payload(
            organization_id=None,
            organization_name='سازمان تازه',
            contract_number='ORG-TEST-0003',
        )
        serializer = SubscriptionWizardSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn('organization_id', serializer.errors)


class SubscriptionWizardDeviceValidationTests(TestCase):
    def setUp(self):
        self.lifecycle_patcher = patch('organizations.serializers.record_device_lifecycle_event')
        self.lifecycle_patcher.start()
        self.addCleanup(self.lifecycle_patcher.stop)
        self.user = User.objects.create_user(
            username='device-test-user',
            password='Password-123456',
            account_type='personal',
            role='personal_user',
        )
        self.device = Device.objects.create(imei='333333333333333')

    def _payload(self, **overrides):
        payload = {
            'customer_type': 'personal',
            'username': self.user.username,
            'existing_user_id': self.user.id,
            'first_name': 'Test',
            'last_name': 'User',
            'mobile': '09120000000',
            'contract_number': 'DEVICE-TEST-0001',
            'start_date': '2026-11-07',
            'end_date': '2027-11-07',
            'devices': [{
                'device_id': self.device.id,
                'start_date': '2026-11-07',
                'end_date': '2027-11-07',
            }],
            'payments': [],
        }
        payload.update(overrides)
        return payload

    def test_empty_device_list_is_rejected(self):
        serializer = SubscriptionWizardSerializer(data=self._payload(devices=[]))
        self.assertFalse(serializer.is_valid())
        self.assertIn('devices', serializer.errors)

    def test_device_not_in_warehouse_is_rejected(self):
        self.device.management_status = 'sold'
        self.device.save(update_fields=['management_status'])
        serializer = SubscriptionWizardSerializer(data=self._payload())
        self.assertFalse(serializer.is_valid())
        self.assertIn('devices', serializer.errors)

    def test_device_with_active_subscription_is_rejected(self):
        existing_subscription = Subscription.objects.create(
            contract_number='DEVICE-TEST-EXISTING',
            customer_type='personal',
            user=self.user,
            start_date='2026-11-07',
            end_date='2027-11-07',
        )
        SubscriptionDevice.objects.create(
            subscription=existing_subscription,
            device=self.device,
            start_date='2026-11-07',
            end_date='2027-11-07',
        )
        serializer = SubscriptionWizardSerializer(data=self._payload())
        self.assertFalse(serializer.is_valid())
        self.assertIn('devices', serializer.errors)

    def test_device_date_range_must_be_inside_contract(self):
        serializer = SubscriptionWizardSerializer(data=self._payload(devices=[{
            'device_id': self.device.id,
            'start_date': '2026-11-06',
            'end_date': '2027-11-07',
        }]))
        self.assertFalse(serializer.is_valid())
        self.assertIn('devices', serializer.errors)

    def test_valid_warehouse_device_is_assigned_to_new_contract(self):
        serializer = SubscriptionWizardSerializer(data=self._payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        subscription = serializer.save()
        link = SubscriptionDevice.objects.get(subscription=subscription, device=self.device)
        self.assertIsNone(link.unassigned_at)
        self.device.refresh_from_db()
        self.assertEqual(self.device.management_status, 'sold')
