from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from fleet.models import Device, DeviceCustomerAccessPeriod
from fleet.customer_access import active_customer_access_periods
from fleet.device_operations import _close_active_link, _open_customer_access
from fleet.serializers import BranchManagerDeviceSerializer, DeviceSerializer
from organizations.models import Branch, Organization, Subscription, SubscriptionDevice


class ContractBackedDeviceAccessTests(TestCase):
    def test_device_detail_service_status_uses_exact_organization_access_contract(self):
        organization = Organization.objects.create(
            name='Exact Device Status Organization',
            code='EXACT-DEVICE-STATUS-ORG',
        )
        branch = Branch.objects.create(
            organization=organization,
            name='Exact Device Status Branch',
            code='EXACT-DEVICE-STATUS-BR',
        )
        main_user = User.objects.create_user(
            username='exact_device_status_main',
            password='test-password',
            role='main_user',
            account_type='organization',
            organization=organization,
        )
        branch_user = User.objects.create_user(
            username='exact_device_status_branch',
            password='test-password',
            role='branch_manager',
            account_type='organization',
            organization=organization,
            branch=branch,
        )
        device = Device.objects.create(
            imei='860000000001207',
            organization=organization,
            branch=branch,
            management_status='installed',
        )
        today = timezone.localdate()
        now = timezone.now()
        authorized = Subscription.objects.create(
            contract_number='EXACT-DEVICE-STATUS-OLD',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=20),
            status='active',
        )
        newer = Subscription.objects.create(
            contract_number='EXACT-DEVICE-STATUS-NEW',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=20),
            status='suspended',
        )
        authorized_link = SubscriptionDevice.objects.create(
            subscription=authorized,
            device=device,
            start_date=authorized.start_date,
            end_date=authorized.end_date,
        )
        newer_link = SubscriptionDevice.objects.create(
            subscription=newer,
            device=device,
            start_date=newer.start_date,
            end_date=newer.end_date,
        )
        SubscriptionDevice.objects.filter(
            pk__in=[authorized_link.pk, newer_link.pk]
        ).update(unassigned_at=None)
        SubscriptionDevice.objects.filter(pk=authorized_link.pk).update(
            assigned_at=now - timedelta(days=2)
        )
        SubscriptionDevice.objects.filter(pk=newer_link.pk).update(
            assigned_at=now - timedelta(days=1)
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=organization,
            branch=branch,
            subscription=authorized,
            started_at=now - timedelta(days=3),
        )

        main_request = SimpleNamespace(user=main_user)
        branch_request = SimpleNamespace(user=branch_user)
        self.assertTrue(
            DeviceSerializer(context={'request': main_request}).get_data_active(device)
        )
        self.assertTrue(
            BranchManagerDeviceSerializer(
                context={'request': branch_request}
            ).get_data_active(device)
        )


    def setUp(self):
        self.client = APIClient()
        today = timezone.localdate()
        self.start_date = today - timedelta(days=5)
        self.end_date = today + timedelta(days=20)

    def _assert_device_hidden_after_contract_suspension(
        self, *, username, role, account_type, customer_type, imei,
        organization=None, branch=None, personal_user=None,
    ):
        user = User.objects.create_user(
            username=username,
            password='test-password',
            role=role,
            account_type=account_type,
            organization=organization,
            branch=branch,
        )
        device_kwargs = {'imei': imei}
        if customer_type == 'organization':
            device_kwargs.update(organization=organization, branch=branch)
        else:
            device_kwargs['owner_user'] = user
        device = Device.objects.create(**device_kwargs)

        subscription = Subscription.objects.create(
            contract_number=f'ACCESS-{imei}',
            customer_type=customer_type,
            organization=organization if customer_type == 'organization' else None,
            user=user if customer_type == 'personal' else None,
            start_date=self.start_date,
            end_date=self.end_date,
            status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=self.start_date,
            end_date=self.end_date,
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=organization if customer_type == 'organization' else None,
            user=user if customer_type == 'personal' else None,
            subscription=subscription,
            branch=branch,
            started_at=timezone.now() - timedelta(days=1),
        )

        self.client.force_authenticate(user=user)
        with patch('fleet.views.traccar_devices', return_value=[]), patch(
            'fleet.views.traccar_current_positions', return_value=[]
        ):
            response = self.client.get('/api/devices/')

        self.assertEqual(response.status_code, 200, response.data)
        payload = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertEqual([item['id'] for item in payload], [device.pk])

        subscription.status = 'suspended'
        subscription.save(update_fields=['status'])
        with patch('fleet.views.traccar_devices', return_value=[]), patch(
            'fleet.views.traccar_current_positions', return_value=[]
        ):
            response = self.client.get('/api/devices/')

        self.assertEqual(response.status_code, 200, response.data)
        payload = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertNotIn(device.pk, [item['id'] for item in payload])

        # Re-activating the same still-valid contract restores access without
        # replacing or deleting its historical access period.
        subscription.status = 'active'
        subscription.save(update_fields=['status'])
        with patch('fleet.views.traccar_devices', return_value=[]), patch(
            'fleet.views.traccar_current_positions', return_value=[]
        ):
            response = self.client.get('/api/devices/')

        self.assertEqual(response.status_code, 200, response.data)
        payload = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertIn(device.pk, [item['id'] for item in payload])
        self.assertEqual(
            DeviceCustomerAccessPeriod.objects.filter(device=device).count(),
            1,
        )

    def test_organization_access_requires_active_contract(self):
        organization = Organization.objects.create(
            name='Contract Access Organization',
            code='CONTRACT-ACCESS-ORG',
        )
        self._assert_device_hidden_after_contract_suspension(
            username='contract_access_org',
            role='main_user',
            account_type='organization',
            customer_type='organization',
            imei='860000000001101',
            organization=organization,
        )

    def test_branch_access_requires_active_contract(self):
        organization = Organization.objects.create(
            name='Contract Access Branch Organization',
            code='CONTRACT-ACCESS-BR-ORG',
        )
        branch = Branch.objects.create(
            organization=organization,
            name='Contract Access Branch',
            code='CONTRACT-ACCESS-BR',
        )
        self._assert_device_hidden_after_contract_suspension(
            username='contract_access_branch',
            role='branch_manager',
            account_type='organization',
            customer_type='organization',
            imei='860000000001102',
            organization=organization,
            branch=branch,
        )

    def test_personal_access_requires_active_contract(self):
        self._assert_device_hidden_after_contract_suspension(
            username='contract_access_personal',
            role='personal_user',
            account_type='personal',
            customer_type='personal',
            imei='860000000001103',
        )
    def test_expired_contract_does_not_authorize_personal_device(self):
        user = User.objects.create_user(
            username='contract_access_expired_personal',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        today = timezone.localdate()
        device = Device.objects.create(
            imei='860000000001104',
            owner_user=user,
        )
        subscription = Subscription.objects.create(
            contract_number='ACCESS-EXPIRED-PERSONAL',
            customer_type='personal',
            user=user,
            start_date=today - timedelta(days=20),
            end_date=today - timedelta(days=1),
            status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=today - timedelta(days=20),
            end_date=today - timedelta(days=1),
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            user=user,
            subscription=subscription,
            started_at=timezone.now() - timedelta(days=10),
        )

        self.client.force_authenticate(user=user)
        with patch('fleet.views.traccar_devices', return_value=[]), patch(
            'fleet.views.traccar_current_positions', return_value=[]
        ):
            response = self.client.get('/api/devices/')

        self.assertEqual(response.status_code, 200, response.data)
        payload = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertNotIn(device.pk, [item['id'] for item in payload])



class CustomerAccessTimelineAndContractTests(TestCase):
    def test_closing_device_assignment_closes_all_legacy_open_contract_links(self):
        organization = Organization.objects.create(
            name='Legacy Open Links Organization',
            code='LEGACY-OPEN-LINKS',
        )
        device = Device.objects.create(
            imei='860000000001205',
            organization=organization,
        )
        today = timezone.localdate()
        subscriptions = [
            Subscription.objects.create(
                contract_number=f'LEGACY-OPEN-LINKS-{index}',
                customer_type='organization',
                organization=organization,
                start_date=today - timedelta(days=5),
                end_date=today + timedelta(days=20),
                status='active',
            )
            for index in (1, 2)
        ]
        links = [
            SubscriptionDevice.objects.create(
                subscription=subscription,
                device=device,
                start_date=subscription.start_date,
                end_date=subscription.end_date,
            )
            for subscription in subscriptions
        ]
        # Simulate legacy inconsistency: both historical assignments remain open.
        SubscriptionDevice.objects.filter(
            pk__in=[link.pk for link in links]
        ).update(unassigned_at=None)

        _close_active_link(device, operation=None)

        self.assertFalse(
            SubscriptionDevice.objects.filter(
                device=device,
                unassigned_at__isnull=True,
            ).exists()
        )

    def test_changing_contract_creates_a_new_access_period(self):
        organization = Organization.objects.create(
            name='Access Timeline Organization',
            code='ACCESS-TIMELINE-ORG',
        )
        device = Device.objects.create(
            imei='860000000001201',
            organization=organization,
        )
        today = timezone.localdate()
        first = Subscription.objects.create(
            contract_number='ACCESS-TIMELINE-001',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=20),
            end_date=today + timedelta(days=10),
            status='active',
        )
        second = Subscription.objects.create(
            contract_number='ACCESS-TIMELINE-002',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=2),
            end_date=today + timedelta(days=30),
            status='active',
        )
        started_at = timezone.now() - timedelta(days=5)
        old_period = DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=organization,
            subscription=first,
            started_at=started_at,
        )

        changed_at = timezone.now()
        new_period = _open_customer_access(
            device,
            subscription=second,
            organization=organization,
            started_at=changed_at,
            reason='new_contract',
        )

        old_period.refresh_from_db()
        self.assertEqual(old_period.ended_at, changed_at)
        self.assertNotEqual(new_period.pk, old_period.pk)
        self.assertEqual(new_period.subscription_id, second.pk)
        self.assertEqual(new_period.started_at, changed_at)

    def test_branch_change_creates_a_new_branch_scoped_access_period(self):
        organization = Organization.objects.create(
            name='Branch Access Timeline Organization',
            code='BRANCH-ACCESS-TIMELINE',
        )
        first_branch = Branch.objects.create(
            organization=organization,
            name='First Access Branch',
            code='ACCESS-BR-1',
        )
        second_branch = Branch.objects.create(
            organization=organization,
            name='Second Access Branch',
            code='ACCESS-BR-2',
        )
        device = Device.objects.create(
            imei='860000000001208',
            organization=organization,
            branch=first_branch,
        )
        today = timezone.localdate()
        subscription = Subscription.objects.create(
            contract_number='BRANCH-ACCESS-TIMELINE-001',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=20),
            status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
        )

        first_period = _open_customer_access(
            device,
            subscription=subscription,
            branch=first_branch,
            reason='contract_assignment',
        )
        device.branch = second_branch
        second_period = _open_customer_access(
            device,
            subscription=subscription,
            branch=second_branch,
            reason='branch_transfer',
        )

        first_period.refresh_from_db()
        self.assertIsNotNone(first_period.ended_at)
        self.assertNotEqual(first_period.pk, second_period.pk)
        self.assertEqual(second_period.branch_id, second_branch.pk)
        self.assertFalse(
            active_customer_access_periods(
                organization_id=organization.pk,
                branch_id=first_branch.pk,
            ).filter(device=device).exists()
        )
        self.assertTrue(
            active_customer_access_periods(
                organization_id=organization.pk,
                branch_id=second_branch.pk,
            ).filter(device=device).exists()
        )

    def test_reactivating_contract_restores_same_access_period(self):
        organization = Organization.objects.create(
            name='Access Reactivation Organization',
            code='ACCESS-REACTIVATION-ORG',
        )
        device = Device.objects.create(
            imei='860000000001206',
            organization=organization,
        )
        today = timezone.localdate()
        subscription = Subscription.objects.create(
            contract_number='ACCESS-REACTIVATION-001',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=20),
            status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
        )
        access = DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=organization,
            subscription=subscription,
            started_at=timezone.now() - timedelta(days=2),
        )

        self.assertEqual(
            active_customer_access_periods(organization_id=organization.pk)
            .filter(device=device).count(),
            1,
        )

        subscription.status = 'suspended'
        subscription.save(update_fields=['status'])
        self.assertFalse(
            active_customer_access_periods(organization_id=organization.pk)
            .filter(device=device).exists()
        )
        access.refresh_from_db()
        self.assertIsNone(access.ended_at)

        subscription.status = 'active'
        subscription.save(update_fields=['status'])
        restored = active_customer_access_periods(
            organization_id=organization.pk
        ).filter(device=device)

        self.assertEqual(restored.count(), 1)
        self.assertEqual(restored.get().pk, access.pk)
        self.assertEqual(
            DeviceCustomerAccessPeriod.objects.filter(device=device).count(),
            1,
        )

    def test_future_contract_device_assignment_does_not_authorize_access_period(self):
        user = User.objects.create_user(
            username='future_assignment_access',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        today = timezone.localdate()
        now = timezone.now()
        device = Device.objects.create(
            imei='860000000001202',
            owner_user=user,
        )
        subscription = Subscription.objects.create(
            contract_number='ACCESS-FUTURE-ASSIGNMENT',
            customer_type='personal',
            user=user,
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
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            user=user,
            subscription=subscription,
            started_at=now - timedelta(minutes=1),
        )

        self.assertFalse(
            active_customer_access_periods(user_id=user.pk, now=now)
            .filter(device=device)
            .exists()
        )

    def test_device_data_activity_requires_an_active_contract(self):
        user = User.objects.create_user(
            username='device_data_contract_status',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        today = timezone.localdate()
        device = Device.objects.create(
            imei='860000000001203',
            owner_user=user,
            management_status='active',
        )
        subscription = Subscription.objects.create(
            contract_number='ACCESS-DATA-ACTIVE',
            customer_type='personal',
            user=user,
            start_date=today - timedelta(days=2),
            end_date=today + timedelta(days=20),
            status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=today - timedelta(days=2),
            end_date=today + timedelta(days=20),
        )

        device.refresh_from_db()
        self.assertTrue(device.is_data_active)

        subscription.status = 'suspended'
        subscription.save(update_fields=['status'])
        device.refresh_from_db()
        self.assertFalse(device.is_data_active)

        # Even if dates are in range, a stored expired status is not active.
        subscription.status = 'expired'
        subscription.save(update_fields=['status'])
        device.refresh_from_db()
        subscription.refresh_from_db()
        self.assertEqual(subscription.computed_status, 'expired')
        self.assertFalse(subscription.is_active)
        self.assertFalse(device.is_data_active)
