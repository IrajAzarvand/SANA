from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from fleet.models import Device, DeviceCustomerAccessPeriod
from fleet.customer_access import active_customer_access_periods
from fleet.device_operations import _close_active_link, _open_customer_access, execute_device_operation
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
            unassigned_at=now - timedelta(minutes=1),
        )
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
        # A newer started assignment supersedes the older contract for
        # both organization and personal access, even when the newer link
        # has already been unassigned or its contract is suspended.
        self.assertFalse(
            DeviceSerializer(context={'request': main_request}).get_data_active(device)
        )
        self.assertFalse(
            BranchManagerDeviceSerializer(
                context={'request': branch_request}
            ).get_data_active(device)
        )


    def test_organization_device_detail_does_not_treat_future_assignment_as_active(self):
        organization = Organization.objects.create(
            name='Future Duplicate Detail Organization',
            code='FUTURE-DUPLICATE-DETAIL-ORG',
        )
        main_user = User.objects.create_user(
            username='future_duplicate_detail_main',
            password='test-password',
            role='main_user',
            account_type='organization',
            organization=organization,
        )
        device = Device.objects.create(
            imei='860000000001210',
            organization=organization,
            management_status='installed',
        )
        today = timezone.localdate()
        now = timezone.now()
        subscription = Subscription.objects.create(
            contract_number='FUTURE-DUPLICATE-DETAIL-001',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=20),
            status='active',
        )
        future_link = SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
        )
        SubscriptionDevice.objects.filter(pk=future_link.pk).update(
            assigned_at=now + timedelta(minutes=10)
        )
        future_link.refresh_from_db()
        period = DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=organization,
            subscription=subscription,
            started_at=now - timedelta(days=3),
        )
        device._active_customer_access_periods = [period]
        device._prefetched_subscription_links = [future_link]

        request = SimpleNamespace(user=main_user)
        self.assertFalse(
            DeviceSerializer(context={'request': request}).get_data_active(device)
        )

    def setUp(self):
        self.client = APIClient()
        today = timezone.localdate()
        self.start_date = today - timedelta(days=5)
        self.end_date = today + timedelta(days=20)

    def _assert_device_hidden_after_contract_suspension(
        self, *, username, role, account_type, customer_type, imei,
        organization=None, branch=None,
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
        access_period = None
        if customer_type == 'organization':
            access_period = DeviceCustomerAccessPeriod.objects.create(
                device=device,
                organization=organization,
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

        # Re-activating the same still-valid contract restores access.
        # Organization access history must remain intact; personal access
        # intentionally does not depend on an access-period row.
        subscription.status = 'active'
        subscription.save(update_fields=['status'])
        with patch('fleet.views.traccar_devices', return_value=[]), patch(
            'fleet.views.traccar_current_positions', return_value=[]
        ):
            response = self.client.get('/api/devices/')

        self.assertEqual(response.status_code, 200, response.data)
        payload = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertIn(device.pk, [item['id'] for item in payload])
        access_period_ids = list(
            DeviceCustomerAccessPeriod.objects.filter(
                device=device
            ).values_list('pk', flat=True)
        )
        self.assertEqual(
            access_period_ids,
            [access_period.pk] if access_period else [],
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
    def test_personal_device_list_ignores_newer_future_assignment_when_selecting_contract(self):
        user = User.objects.create_user(
            username='personal_future_link_selection',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        today = timezone.localdate()
        now = timezone.now()
        device = Device.objects.create(
            imei='860000000001105',
            owner_user=user,
            management_status='installed',
        )
        valid_subscription = Subscription.objects.create(
            contract_number='PERSONAL-VALID-LINK-SELECTION',
            customer_type='personal',
            user=user,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=20),
            status='active',
        )
        future_subscription = Subscription.objects.create(
            contract_number='PERSONAL-FUTURE-LINK-SELECTION',
            customer_type='personal',
            user=user,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=20),
            status='active',
        )
        valid_link = SubscriptionDevice.objects.create(
            subscription=valid_subscription,
            device=device,
            start_date=valid_subscription.start_date,
            end_date=valid_subscription.end_date,
        )
        future_link = SubscriptionDevice.objects.create(
            subscription=future_subscription,
            device=device,
            start_date=future_subscription.start_date,
            end_date=future_subscription.end_date,
            unassigned_at=now + timedelta(minutes=30),
        )
        SubscriptionDevice.objects.filter(pk=valid_link.pk).update(
            assigned_at=now - timedelta(days=2)
        )
        SubscriptionDevice.objects.filter(pk=future_link.pk).update(
            assigned_at=now + timedelta(minutes=10)
        )

        self.client.force_authenticate(user=user)
        with patch('fleet.views.traccar_devices', return_value=[]), patch(
            'fleet.views.traccar_current_positions', return_value=[]
        ):
            response = self.client.get('/api/devices/')

        self.assertEqual(response.status_code, 200, response.data)
        payload = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['id'], device.pk)
        self.assertTrue(payload[0]['data_active'])
        self.assertEqual(payload[0]['subscription_id'], valid_subscription.pk)
        self.assertNotEqual(payload[0]['subscription_id'], future_subscription.pk)

    def test_future_contract_does_not_authorize_personal_device(self):
        user = User.objects.create_user(
            username='contract_access_future_personal',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        today = timezone.localdate()
        device = Device.objects.create(
            imei='860000000001106',
            owner_user=user,
        )
        subscription = Subscription.objects.create(
            contract_number='ACCESS-FUTURE-PERSONAL',
            customer_type='personal',
            user=user,
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=20),
            status='active',
        )
        link = SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=20),
        )
        # The device link itself is valid today; only the parent contract is future.
        Subscription.objects.filter(pk=subscription.pk).update(
            start_date=today + timedelta(days=1)
        )

        self.client.force_authenticate(user=user)
        with patch('fleet.views.traccar_devices', return_value=[]), patch(
            'fleet.views.traccar_current_positions', return_value=[]
        ):
            response = self.client.get('/api/devices/')

        self.assertEqual(response.status_code, 200, response.data)
        payload = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertNotIn(device.pk, [item['id'] for item in payload])

    def test_future_assigned_at_does_not_authorize_personal_device(self):
        user = User.objects.create_user(
            username='contract_access_future_assignment',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        today = timezone.localdate()
        now = timezone.now()
        device = Device.objects.create(
            imei='860000000001107',
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

        self.client.force_authenticate(user=user)
        with patch('fleet.views.traccar_devices', return_value=[]), patch(
            'fleet.views.traccar_current_positions', return_value=[]
        ):
            response = self.client.get('/api/devices/')

        self.assertEqual(response.status_code, 200, response.data)
        payload = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertNotIn(device.pk, [item['id'] for item in payload])

    def test_future_or_expired_device_link_dates_do_not_authorize_personal_devices(self):
        user = User.objects.create_user(
            username='contract_access_invalid_link_dates',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        today = timezone.localdate()
        future_device = Device.objects.create(
            imei='860000000001211',
            owner_user=user,
        )
        expired_device = Device.objects.create(
            imei='860000000001212',
            owner_user=user,
        )
        future_subscription = Subscription.objects.create(
            contract_number='ACCESS-FUTURE-LINK-DATE',
            customer_type='personal',
            user=user,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=20),
            status='active',
        )
        expired_subscription = Subscription.objects.create(
            contract_number='ACCESS-EXPIRED-LINK-DATE',
            customer_type='personal',
            user=user,
            start_date=today - timedelta(days=20),
            end_date=today + timedelta(days=20),
            status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=future_subscription,
            device=future_device,
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=20),
        )
        expired_link = SubscriptionDevice.objects.create(
            subscription=expired_subscription,
            device=expired_device,
            start_date=today - timedelta(days=20),
            end_date=today - timedelta(days=1),
        )
        # Keep the parent contract valid to isolate the device-link end date.
        Subscription.objects.filter(pk=expired_subscription.pk).update(
            end_date=today + timedelta(days=20)
        )

        self.client.force_authenticate(user=user)
        with patch('fleet.views.traccar_devices', return_value=[]), patch(
            'fleet.views.traccar_current_positions', return_value=[]
        ):
            response = self.client.get('/api/devices/')

        self.assertEqual(response.status_code, 200, response.data)
        payload = response.data['results'] if isinstance(response.data, dict) else response.data
        visible_ids = {item['id'] for item in payload}
        self.assertNotIn(future_device.pk, visible_ids)
        self.assertNotIn(expired_device.pk, visible_ids)

    def test_ended_assignment_does_not_authorize_personal_device(self):
        user = User.objects.create_user(
            username='contract_access_ended_assignment',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        today = timezone.localdate()
        now = timezone.now()
        device = Device.objects.create(
            imei='860000000001108',
            owner_user=user,
        )
        subscription = Subscription.objects.create(
            contract_number='ACCESS-ENDED-ASSIGNMENT',
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
            unassigned_at=now - timedelta(seconds=1)
        )

        self.client.force_authenticate(user=user)
        with patch('fleet.views.traccar_devices', return_value=[]), patch(
            'fleet.views.traccar_current_positions', return_value=[]
        ):
            response = self.client.get('/api/devices/')

        self.assertEqual(response.status_code, 200, response.data)
        payload = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertNotIn(device.pk, [item['id'] for item in payload])

    def test_newer_started_suspended_personal_assignment_blocks_older_valid_link(self):
        user = User.objects.create_user(
            username='personal_newer_suspended_assignment',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        today = timezone.localdate()
        now = timezone.now()
        device = Device.objects.create(
            imei='860000000001109',
            owner_user=user,
        )
        older_subscription = Subscription.objects.create(
            contract_number='PERSONAL-OLDER-VALID-ASSIGNMENT',
            customer_type='personal',
            user=user,
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=20),
            status='active',
        )
        newer_subscription = Subscription.objects.create(
            contract_number='PERSONAL-NEWER-SUSPENDED-ASSIGNMENT',
            customer_type='personal',
            user=user,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=20),
            status='suspended',
        )
        older_link = SubscriptionDevice.objects.create(
            subscription=older_subscription,
            device=device,
            start_date=older_subscription.start_date,
            end_date=older_subscription.end_date,
        )
        newer_link = SubscriptionDevice.objects.create(
            subscription=newer_subscription,
            device=device,
            start_date=newer_subscription.start_date,
            end_date=newer_subscription.end_date,
            unassigned_at=now - timedelta(minutes=1),
        )
        SubscriptionDevice.objects.filter(pk=older_link.pk).update(
            assigned_at=now - timedelta(days=3)
        )
        SubscriptionDevice.objects.filter(pk=newer_link.pk).update(
            assigned_at=now - timedelta(days=1)
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            user=user,
            subscription=older_subscription,
            started_at=now - timedelta(days=5),
        )

        self.client.force_authenticate(user=user)
        with patch('fleet.views.traccar_devices', return_value=[]), patch(
            'fleet.views.traccar_current_positions', return_value=[]
        ):
            response = self.client.get('/api/devices/')

        self.assertEqual(response.status_code, 200, response.data)
        payload = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertNotIn(device.pk, [item['id'] for item in payload])

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
        self.client.force_authenticate(user=user)
        with patch('fleet.views.traccar_devices', return_value=[]), patch(
            'fleet.views.traccar_current_positions', return_value=[]
        ):
            response = self.client.get('/api/devices/')

        self.assertEqual(response.status_code, 200, response.data)
        payload = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertNotIn(device.pk, [item['id'] for item in payload])



class DeviceActiveAssignmentSelectionTests(TestCase):
    def test_future_assignment_does_not_displace_current_started_assignment(self):
        organization = Organization.objects.create(
            name='Future Device Assignment Organization',
            code='FUTURE-DEVICE-ASSIGNMENT',
        )
        device = Device.objects.create(
            imei='860000000001214',
            organization=organization,
            management_status='installed',
        )
        today = timezone.localdate()
        now = timezone.now()
        current_subscription = Subscription.objects.create(
            contract_number='DEVICE-CURRENT-ASSIGNMENT',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=20),
            status='active',
        )
        future_subscription = Subscription.objects.create(
            contract_number='DEVICE-FUTURE-ASSIGNMENT',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=20),
            status='active',
        )
        current_link = SubscriptionDevice.objects.create(
            subscription=current_subscription,
            device=device,
            start_date=current_subscription.start_date,
            end_date=current_subscription.end_date,
        )
        future_link = SubscriptionDevice.objects.create(
            subscription=future_subscription,
            device=device,
            start_date=future_subscription.start_date,
            end_date=future_subscription.end_date,
            unassigned_at=now + timedelta(minutes=30),
        )
        SubscriptionDevice.objects.filter(pk=current_link.pk).update(
            assigned_at=now - timedelta(days=2)
        )
        SubscriptionDevice.objects.filter(pk=future_link.pk).update(
            assigned_at=now + timedelta(minutes=10)
        )

        # A future-dated history row cannot displace the only open assignment.
        self.assertEqual(device.active_subscription_link.pk, current_link.pk)
        self.assertTrue(device.is_data_active)

    def test_newer_ended_assignment_blocks_older_legacy_open_link(self):
        organization = Organization.objects.create(
            name='Ended Device Assignment Organization',
            code='ENDED-DEVICE-ASSIGNMENT',
        )
        device = Device.objects.create(
            imei='860000000001215',
            organization=organization,
            management_status='installed',
        )
        today = timezone.localdate()
        now = timezone.now()
        subscriptions = [
            Subscription.objects.create(
                contract_number=f'DEVICE-ENDED-ASSIGNMENT-{index}',
                customer_type='organization',
                organization=organization,
                start_date=today - timedelta(days=5),
                end_date=today + timedelta(days=20),
                status='active',
            )
            for index in (1, 2)
        ]
        older_link = SubscriptionDevice.objects.create(
            subscription=subscriptions[0],
            device=device,
            start_date=subscriptions[0].start_date,
            end_date=subscriptions[0].end_date,
        )
        newer_link = SubscriptionDevice.objects.create(
            subscription=subscriptions[1],
            device=device,
            start_date=subscriptions[1].start_date,
            end_date=subscriptions[1].end_date,
            unassigned_at=now - timedelta(seconds=1),
        )
        SubscriptionDevice.objects.filter(pk=older_link.pk).update(
            assigned_at=now - timedelta(days=3),
        )
        SubscriptionDevice.objects.filter(pk=newer_link.pk).update(
            assigned_at=now - timedelta(days=1),
        )

        # A legacy older open row must not revive service after a newer
        # assignment has already ended.
        self.assertEqual(device.active_subscription_link.pk, older_link.pk)
        self.assertFalse(device.is_data_active)


class DispositionCustomerAccessTests(TestCase):
    def test_disposition_transfer_moves_access_to_target_customer_without_branch(self):
        old_organization = Organization.objects.create(
            name='Disposition Old Organization',
            code='DISPOSITION-OLD-ORG',
        )
        new_organization = Organization.objects.create(
            name='Disposition New Organization',
            code='DISPOSITION-NEW-ORG',
        )
        old_branch = Branch.objects.create(
            organization=old_organization,
            name='Disposition Old Branch',
            code='DISPOSITION-OLD-BR',
        )
        new_branch = Branch.objects.create(
            organization=new_organization,
            name='Disposition New Branch',
            code='DISPOSITION-NEW-BR',
        )
        admin = User.objects.create_user(
            username='disposition_transfer_admin',
            password='test-password',
            role='site_admin',
            account_type='admin',
        )
        device = Device.objects.create(
            imei='860000000001216',
            organization=old_organization,
            branch=old_branch,
            management_status='ready',
        )
        today = timezone.localdate()
        old_subscription = Subscription.objects.create(
            contract_number='DISPOSITION-OLD-CONTRACT',
            customer_type='organization',
            organization=old_organization,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=20),
            status='active',
        )
        new_subscription = Subscription.objects.create(
            contract_number='DISPOSITION-NEW-CONTRACT',
            customer_type='organization',
            organization=new_organization,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=20),
            status='active',
        )
        old_link = SubscriptionDevice.objects.create(
            subscription=old_subscription,
            device=device,
            start_date=old_subscription.start_date,
            end_date=old_subscription.end_date,
        )
        old_period = DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=old_organization,
            branch=old_branch,
            subscription=old_subscription,
            started_at=timezone.now(),
        )

        execute_device_operation(
            device=device,
            operation_type='disposition',
            performed_by=admin,
            target_subscription=new_subscription,
            target_organization=new_organization,
            outcome_action='transfer_customer',
            reason='customer_transfer',
        )

        old_period.refresh_from_db()
        self.assertIsNotNone(old_period.ended_at)
        self.assertFalse(
            active_customer_access_periods(
                organization_id=old_organization.pk,
                branch_id=old_branch.pk,
            ).filter(device=device).exists()
        )
        self.assertTrue(
            active_customer_access_periods(
                organization_id=new_organization.pk,
            ).filter(device=device).exists()
        )
        self.assertFalse(
            active_customer_access_periods(
                organization_id=new_organization.pk,
                branch_id=new_branch.pk,
            ).filter(device=device).exists()
        )
        device.refresh_from_db()
        self.assertIsNone(device.branch_id)
        self.assertEqual(
            SubscriptionDevice.objects.filter(
                device=device,
                unassigned_at__isnull=True,
            ).values_list('subscription_id', flat=True).get(),
            new_subscription.pk,
        )

class CustomerAccessTimelineAndContractTests(TestCase):
    def test_closing_device_assignment_closes_current_link_and_preserves_closed_history(self):
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
                subscription=subscriptions[0],
                device=device,
                start_date=subscriptions[0].start_date,
                end_date=subscriptions[0].end_date,
            ),
            SubscriptionDevice.objects.create(
                subscription=subscriptions[1],
                device=device,
                start_date=subscriptions[1].start_date,
                end_date=subscriptions[1].end_date,
                unassigned_at=timezone.now() - timedelta(minutes=1),
            ),
        ]

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
        SubscriptionDevice.objects.create(
            subscription=second,
            device=device,
            start_date=second.start_date,
            end_date=second.end_date,
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

    def test_reassigning_device_to_same_contract_opens_new_access_period(self):
        organization = Organization.objects.create(
            name='Same Contract Reassignment Organization',
            code='SAME-CONTRACT-REASSIGN',
        )
        device = Device.objects.create(
            imei='860000000001213',
            organization=organization,
        )
        today = timezone.localdate()
        subscription = Subscription.objects.create(
            contract_number='SAME-CONTRACT-REASSIGN-001',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=20),
            status='active',
        )
        first_link = SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
        )
        first_period = _open_customer_access(
            device,
            subscription=subscription,
            organization=organization,
            reason='first_assignment',
        )

        SubscriptionDevice.objects.filter(pk=first_link.pk).update(
            unassigned_at=timezone.now()
        )
        second_link = SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
        )
        second_period = _open_customer_access(
            device,
            subscription=subscription,
            organization=organization,
            reason='reassignment',
        )

        first_link.refresh_from_db()
        first_period.refresh_from_db()
        self.assertIsNotNone(first_link.unassigned_at)
        self.assertIsNotNone(first_period.ended_at)
        self.assertNotEqual(first_period.pk, second_period.pk)
        self.assertGreaterEqual(
            second_period.started_at,
            second_link.assigned_at,
        )
        self.assertEqual(second_period.subscription_id, subscription.pk)

    def test_clearing_branch_creates_a_new_unscoped_access_period(self):
        organization = Organization.objects.create(
            name='Clear Branch Access Organization',
            code='CLEAR-BRANCH-ACCESS',
        )
        branch = Branch.objects.create(
            organization=organization,
            name='Old Access Branch',
            code='CLEAR-BRANCH-OLD',
        )
        device = Device.objects.create(
            imei='860000000001209',
            organization=organization,
            branch=branch,
        )
        today = timezone.localdate()
        subscription = Subscription.objects.create(
            contract_number='CLEAR-BRANCH-ACCESS-001',
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

        old_period = _open_customer_access(
            device,
            subscription=subscription,
            branch=branch,
            reason='initial_branch',
        )
        device.branch = None
        device.save(update_fields=['branch', 'updated_at'])
        new_period = _open_customer_access(
            device,
            subscription=subscription,
            branch=None,
            reason='branch_cleared',
        )

        old_period.refresh_from_db()
        self.assertIsNotNone(old_period.ended_at)
        self.assertNotEqual(old_period.pk, new_period.pk)
        self.assertIsNone(new_period.branch_id)
        self.assertFalse(
            active_customer_access_periods(
                organization_id=organization.pk,
                branch_id=branch.pk,
            ).filter(device=device).exists()
        )
        self.assertTrue(
            active_customer_access_periods(
                organization_id=organization.pk,
            ).filter(device=device).exists()
        )

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
        # The previous branch period is closed and remains historical.
        stale_period = first_period
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
        retained_period = _open_customer_access(
            device,
            subscription=subscription,
            branch=second_branch,
            reason='branch_transfer',
        )

        first_period.refresh_from_db()
        stale_period.refresh_from_db()
        self.assertIsNotNone(first_period.ended_at)
        self.assertIsNotNone(stale_period.ended_at)
        self.assertEqual(retained_period.pk, second_period.pk)
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

        # If the latest period later ends, the older stale period must not
        # become active again for the previous branch.
        DeviceCustomerAccessPeriod.objects.filter(
            pk=second_period.pk
        ).update(ended_at=max(
            timezone.now() - timedelta(seconds=1),
            second_period.started_at,
        ))
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=organization,
            branch=first_branch,
            subscription=subscription,
            started_at=second_period.started_at - timedelta(days=1),
        )
        self.assertFalse(
            active_customer_access_periods(
                organization_id=organization.pk,
                branch_id=first_branch.pk,
            ).filter(device=device).exists()
        )
        self.assertFalse(
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


class ArchivedOrganizationCustomerAccessTests(TestCase):
    def test_archived_organization_cannot_keep_active_customer_access(self):
        today = timezone.localdate()
        organization = Organization.objects.create(
            name='Archived Access Organization',
            code='ARCHIVED-ACCESS-ORG',
            status='archived',
        )
        branch = Branch.objects.create(
            organization=organization,
            name='Archived Access Branch',
            code='ARCHIVED-ACCESS-BR',
        )
        device = Device.objects.create(imei='860000000009952')
        subscription = Subscription.objects.create(
            contract_number='ARCHIVED-ACCESS-CONTRACT',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=10),
            status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=organization,
            branch=branch,
            subscription=subscription,
        )

        self.assertFalse(
            active_customer_access_periods(
                organization_id=organization.pk,
                branch_id=branch.pk,
            ).filter(device=device).exists()
        )


class VehiclePlateDisclosureAcrossDeviceEndpointsTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name='Vehicle Plate Access Customer',
            code='VEH-PLATE-ACCESS-CUSTOMER',
        )
        self.foreign_organization = Organization.objects.create(
            name='Vehicle Plate Legal Owner',
            code='VEH-PLATE-LEGAL-OWNER',
        )
        self.manager = User.objects.create_user(
            username='vehicle_plate_access_manager',
            password='test-password',
            role='main_user',
            account_type='organization',
            organization=self.organization,
        )
        from fleet.models import Vehicle
        self.vehicle = Vehicle.objects.create(
            plate='33ک333',
            organization=self.foreign_organization,
        )
        self.device = Device.objects.create(
            imei='860000000009971',
            organization=self.organization,
            vehicle=self.vehicle,
        )
        today = timezone.localdate()
        self.contract = Subscription.objects.create(
            contract_number='VEH-PLATE-ACCESS-CONTRACT',
            customer_type='organization',
            organization=self.organization,
            start_date=today - timedelta(days=3),
            end_date=today + timedelta(days=20),
            status='active',
        )
        link = SubscriptionDevice.objects.create(
            subscription=self.contract,
            device=self.device,
            start_date=self.contract.start_date,
            end_date=self.contract.end_date,
        )
        # The event below predates the request, so make the assignment window
        # explicitly begin before that event instead of using the model's
        # default assigned_at timestamp (which is set to test setup time).
        SubscriptionDevice.objects.filter(pk=link.pk).update(
            assigned_at=timezone.now() - timedelta(days=2)
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=self.device,
            organization=self.organization,
            subscription=self.contract,
            started_at=timezone.now() - timedelta(days=1),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.manager)

    def test_live_map_hides_vehicle_plate_outside_customer_tenant(self):
        with patch('fleet.views.traccar_devices', return_value=[]), patch(
            'fleet.views.traccar_current_positions', return_value=[],
        ):
            response = self.client.get('/api/devices/map-positions/')

        self.assertEqual(response.status_code, 200, response.data)
        row = next(item for item in response.data if item['device_id'] == self.device.pk)
        self.assertIsNone(row['vehicle_plate'])

    def test_alerts_hide_vehicle_plate_outside_customer_tenant(self):
        event_time = timezone.now() - timedelta(minutes=5)
        with patch('fleet.views.traccar_devices', return_value=[{
            'id': 9971,
            'uniqueId': self.device.imei,
        }]), patch('fleet.views.traccar_device_events', return_value=[{
            'id': 'vehicle-plate-event-9971',
            'deviceId': 9971,
            'type': 'alarm',
            'eventTime': event_time.isoformat(),
            'attributes': {},
        }]):
            response = self.client.get('/api/devices/alerts/')

        self.assertEqual(response.status_code, 200, response.data)
        row = next(
            item for item in response.data['results']
            if item['device_id'] == self.device.pk
        )
        self.assertIsNone(row['vehicle_plate'])
class InactiveBranchCustomerAccessTests(TestCase):
    def test_inactive_branch_cannot_access_device_through_open_contract_period(self):
        organization = Organization.objects.create(
            name='Inactive Branch Access Organization',
            code='INACTIVE-BRANCH-ACCESS-ORG',
        )
        branch = Branch.objects.create(
            organization=organization,
            name='Inactive Access Branch',
            code='INACTIVE-ACCESS-BR',
            status='inactive',
        )
        manager = User.objects.create_user(
            username='inactive_branch_access_manager',
            password='test-password',
            role='branch_manager',
            account_type='organization',
            organization=organization,
            branch=branch,
        )
        device = Device.objects.create(
            imei='860000000009951',
            organization=organization,
            branch=branch,
        )
        today = timezone.localdate()
        contract = Subscription.objects.create(
            contract_number='INACTIVE-BRANCH-ACCESS-CONTRACT',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=2),
            end_date=today + timedelta(days=20),
            status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=contract,
            device=device,
            start_date=contract.start_date,
            end_date=contract.end_date,
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=organization,
            branch=branch,
            subscription=contract,
            started_at=timezone.now() - timedelta(days=1),
        )

        self.assertFalse(
            active_customer_access_periods(
                organization_id=organization.pk,
                branch_id=branch.pk,
            ).filter(device=device).exists()
        )
        from fleet.customer_access import authorized_devices_for_user
        self.assertFalse(authorized_devices_for_user(manager).filter(pk=device.pk).exists())


class ReportHistoryVehiclePlateDisclosureTests(TestCase):
    def test_report_history_metadata_hides_vehicle_plate_outside_customer_tenant(self):
        from fleet.models import Vehicle

        organization = Organization.objects.create(
            name='Report Plate Access Customer',
            code='REPORT-PLATE-ACCESS-CUSTOMER',
        )
        foreign_organization = Organization.objects.create(
            name='Report Plate Legal Owner',
            code='REPORT-PLATE-LEGAL-OWNER',
        )
        manager = User.objects.create_user(
            username='report_plate_access_manager',
            password='test-password',
            role='main_user',
            account_type='organization',
            organization=organization,
        )
        vehicle = Vehicle.objects.create(
            plate='22م222',
            organization=foreign_organization,
        )
        device = Device.objects.create(
            imei='860000000009981',
            sim_number='09120009981',
            organization=organization,
            vehicle=vehicle,
        )
        today = timezone.localdate()
        contract = Subscription.objects.create(
            contract_number='REPORT-PLATE-ACCESS-CONTRACT',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=3),
            end_date=today + timedelta(days=20),
            status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=contract,
            device=device,
            start_date=contract.start_date,
            end_date=contract.end_date,
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=organization,
            subscription=contract,
            started_at=timezone.now() - timedelta(days=1),
        )
        client = APIClient()
        client.force_authenticate(user=manager)

        response = client.get('/api/devices/report-history/', {
            'device_id': device.pk,
            'metadata': 'true',
        })

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['device']['imei'], device.imei)
        self.assertEqual(response.data['device']['sim_number'], device.sim_number)
        self.assertIsNone(response.data['device']['vehicle_plate'])


class ReportHistoryPlaybackVehiclePlateDisclosureTests(TestCase):
    def test_report_history_playback_hides_vehicle_plate_outside_customer_tenant(self):
        from datetime import timedelta
        from fleet.models import Vehicle

        organization = Organization.objects.create(
            name='Playback Plate Access Customer',
            code='PLAYBACK-PLATE-ACCESS-CUSTOMER',
        )
        foreign_organization = Organization.objects.create(
            name='Playback Plate Legal Owner',
            code='PLAYBACK-PLATE-LEGAL-OWNER',
        )
        manager = User.objects.create_user(
            username='playback_plate_access_manager',
            password='test-password',
            role='main_user',
            account_type='organization',
            organization=organization,
        )
        vehicle = Vehicle.objects.create(
            plate='44د444',
            organization=foreign_organization,
        )
        device = Device.objects.create(
            imei='860000000009982',
            sim_number='09120009982',
            organization=organization,
            vehicle=vehicle,
        )
        now = timezone.now()
        today = timezone.localdate(now)
        contract = Subscription.objects.create(
            contract_number='PLAYBACK-PLATE-ACCESS-CONTRACT',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=3),
            end_date=today + timedelta(days=20),
            status='active',
        )
        link = SubscriptionDevice.objects.create(
            subscription=contract,
            device=device,
            start_date=contract.start_date,
            end_date=contract.end_date,
        )
        SubscriptionDevice.objects.filter(pk=link.pk).update(
            assigned_at=now - timedelta(days=2),
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=organization,
            subscription=contract,
            started_at=now - timedelta(days=1),
        )
        client = APIClient()
        client.force_authenticate(user=manager)
        point_time = now - timedelta(minutes=5)
        positions = [{
            'id': 9982001,
            'fixTime': point_time.isoformat(),
            'serverTime': point_time.isoformat(),
            'latitude': 35.7,
            'longitude': 51.4,
            'valid': True,
            'speed': 0,
            'course': 0,
            'attributes': {},
        }]

        with patch('fleet.views.traccar_history_device_id', return_value=9982), patch(
            'fleet.views.traccar_device_positions', return_value=positions,
        ), patch('fleet.views._map_matched_positions_by_traccar_ids', return_value={}):
            response = client.get('/api/devices/report-history/', {
                'device_id': device.pk,
                'from': (now - timedelta(minutes=10)).isoformat(),
                'to': (now - timedelta(minutes=1)).isoformat(),
            })

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data['points']), 1)
        self.assertEqual(response.data['device']['imei'], device.imei)
        self.assertIsNone(response.data['device']['vehicle_plate'])


class DevicePartyDisclosureFailClosedTests(TestCase):
    def test_owner_is_visible_to_same_organization_but_not_foreign_tenant(self):
        from fleet.serializers import _redact_unrelated_device_party_fields

        organization = Organization.objects.create(
            name='Owner Disclosure Organization',
            code='OWNER-DISCLOSURE-ORG',
        )
        foreign_organization = Organization.objects.create(
            name='Owner Disclosure Foreign',
            code='OWNER-DISCLOSURE-FOREIGN',
        )
        manager = User.objects.create_user(
            username='owner_disclosure_manager',
            password='test-password',
            role='main_user',
            account_type='organization',
            organization=organization,
        )
        same_tenant_owner = User.objects.create_user(
            username='owner_disclosure_same_tenant',
            password='test-password',
            role='personal_user',
            account_type='personal',
            organization=organization,
        )
        foreign_owner = User.objects.create_user(
            username='owner_disclosure_foreign',
            password='test-password',
            role='personal_user',
            account_type='personal',
            organization=foreign_organization,
        )
        same_tenant_device = Device.objects.create(
            imei='860000000009983',
            owner_user=same_tenant_owner,
        )
        foreign_device = Device.objects.create(
            imei='860000000009984',
            owner_user=foreign_owner,
        )
        same_data = {
            'owner_user': same_tenant_owner.pk,
            'owner_name': same_tenant_owner.full_name,
        }
        foreign_data = {
            'owner_user': foreign_owner.pk,
            'owner_name': foreign_owner.full_name,
        }

        _redact_unrelated_device_party_fields(same_data, same_tenant_device, manager)
        _redact_unrelated_device_party_fields(foreign_data, foreign_device, manager)

        self.assertEqual(same_data['owner_user'], same_tenant_owner.pk)
        self.assertEqual(same_data['owner_name'], same_tenant_owner.full_name)
        self.assertIsNone(foreign_data['owner_user'])
        self.assertIsNone(foreign_data['owner_name'])

    def test_missing_or_anonymous_user_fails_closed_for_party_fields(self):
        from types import SimpleNamespace
        from fleet.serializers import (
            _device_data_active_for_request,
            _device_vehicle_visible_to_user,
            _redact_unrelated_device_party_fields,
        )

        device = Device.objects.create(imei='860000000009985')
        anonymous = SimpleNamespace(is_authenticated=False)
        for user in (None, anonymous):
            data = {
                'organization': 10,
                'organization_name': 'Tenant',
                'owner_user': 11,
                'owner_name': 'Owner',
                'current_holder_organization': 12,
                'current_holder_organization_name': 'Holder',
                'current_holder_user': 13,
                'current_holder_user_name': 'Holder User',
                'branch': 14,
                'branch_name': 'Branch',
                'vehicle': 15,
                'vehicle_plate': '55ه555',
            }
            _redact_unrelated_device_party_fields(data, device, user)
            self.assertTrue(all(value is None for value in data.values()))
            self.assertFalse(_device_vehicle_visible_to_user(device, user))
            self.assertFalse(
                _device_data_active_for_request(device, SimpleNamespace(user=user))
            )


    def test_branch_manager_cannot_see_owner_or_holder_from_another_branch(self):
        from fleet.serializers import _redact_unrelated_device_party_fields

        organization = Organization.objects.create(
            name='Branch Party Disclosure Organization',
            code='BRANCH-PARTY-DISCLOSURE-ORG',
        )
        own_branch = Branch.objects.create(
            organization=organization,
            name='Own Disclosure Branch',
            code='OWN-DISCLOSURE-BR',
        )
        other_branch = Branch.objects.create(
            organization=organization,
            name='Other Disclosure Branch',
            code='OTHER-DISCLOSURE-BR',
        )
        manager = User.objects.create_user(
            username='branch_party_disclosure_manager',
            password='test-password',
            role='branch_manager',
            account_type='organization',
            organization=organization,
            branch=own_branch,
        )
        other_branch_user = User.objects.create_user(
            username='branch_party_disclosure_other_user',
            password='test-password',
            role='personal_user',
            account_type='personal',
            organization=organization,
            branch=other_branch,
        )
        device = Device.objects.create(
            imei='860000000009992',
            owner_user=other_branch_user,
            current_holder_user=other_branch_user,
            branch=own_branch,
        )
        data = {
            'owner_user': other_branch_user.pk,
            'owner_name': other_branch_user.full_name,
            'current_holder_user': other_branch_user.pk,
            'current_holder_user_name': other_branch_user.full_name,
            'branch': own_branch.pk,
            'branch_name': own_branch.name,
        }

        _redact_unrelated_device_party_fields(data, device, manager)

        self.assertIsNone(data['owner_user'])
        self.assertIsNone(data['owner_name'])
        self.assertIsNone(data['current_holder_user'])
        self.assertIsNone(data['current_holder_user_name'])
        self.assertEqual(data['branch'], own_branch.pk)
        self.assertEqual(data['branch_name'], own_branch.name)



class SubscriptionDeviceSerializerVisibilityCacheTests(TestCase):
    def test_repeated_device_visibility_checks_use_one_authorization_query(self):
        from types import SimpleNamespace
        from organizations.serializers import SubscriptionDeviceSerializer

        organization = Organization.objects.create(
            name='Visibility Cache Organization',
            code='VISIBILITY-CACHE-ORG',
        )
        manager = User.objects.create_user(
            username='visibility_cache_manager',
            password='test-password',
            role='main_user',
            account_type='organization',
            organization=organization,
        )
        device = Device.objects.create(
            imei='860000000009990',
            organization=organization,
        )
        today = timezone.localdate()
        now = timezone.now()
        contract = Subscription.objects.create(
            contract_number='VISIBILITY-CACHE-CONTRACT',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=20),
            status='active',
        )
        link = SubscriptionDevice.objects.create(
            subscription=contract,
            device=device,
            start_date=contract.start_date,
            end_date=contract.end_date,
        )
        SubscriptionDevice.objects.filter(pk=link.pk).update(
            assigned_at=now - timedelta(days=2),
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=organization,
            subscription=contract,
            started_at=now - timedelta(days=1),
        )
        serializer = SubscriptionDeviceSerializer(
            instance=link,
            context={'request': SimpleNamespace(user=manager)},
        )

        with self.assertNumQueries(1):
            self.assertTrue(serializer._can_view_device_details(link))
            self.assertTrue(serializer._can_view_device_details(device))

    def test_subscription_device_serializer_without_request_fails_closed(self):
        from organizations.serializers import SubscriptionDeviceSerializer

        device = Device.objects.create(imei='860000000009991')
        today = timezone.localdate()
        contract = Subscription.objects.create(
            contract_number='VISIBILITY-CACHE-NO-REQUEST',
            customer_type='organization',
            organization=Organization.objects.create(
                name='No Request Organization',
                code='NO-REQUEST-ORG',
            ),
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=10),
            status='active',
        )
        link = SubscriptionDevice.objects.create(
            subscription=contract,
            device=device,
            start_date=contract.start_date,
            end_date=contract.end_date,
        )
        serializer = SubscriptionDeviceSerializer(instance=link)
        self.assertFalse(serializer._can_view_device_details(link))


class OrganizationDeviceBranchAssignmentApiTests(TestCase):
    def setUp(self):
        from datetime import timedelta

        self.client = APIClient()
        today = timezone.localdate()
        self.organization = Organization.objects.create(
            name='Branch Assignment API Org',
            code='BRANCH-ASSIGNMENT-API-ORG',
        )
        self.manager = User.objects.create_user(
            username='branch_assignment_api_manager',
            password='test-password',
            role='main_user',
            account_type='organization',
            organization=self.organization,
        )
        self.branch = Branch.objects.create(
            organization=self.organization,
            name='Branch Assignment API Branch',
            code='BRANCH-ASSIGNMENT-API',
        )
        self.device = Device.objects.create(
            imei='860000000009971',
            organization=self.organization,
            management_status='installed',
        )
        self.subscription = Subscription.objects.create(
            contract_number='BRANCH-ASSIGNMENT-API-CONTRACT',
            customer_type='organization',
            organization=self.organization,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=30),
            status='active',
        )
        self.link = SubscriptionDevice.objects.create(
            subscription=self.subscription,
            device=self.device,
            start_date=self.subscription.start_date,
            end_date=self.subscription.end_date,
        )
        self.original_period = DeviceCustomerAccessPeriod.objects.create(
            device=self.device,
            organization=self.organization,
            subscription=self.subscription,
            branch=None,
            started_at=timezone.now() - timedelta(days=2),
        )
        self.client.force_authenticate(user=self.manager)

    def test_manager_assigns_unbranched_device_and_organization_access_resumes_after_end_date(self):
        from datetime import datetime, timedelta, time as datetime_time

        end_date = timezone.localdate() + timedelta(days=5)
        response = self.client.post(
            f'/api/devices/{self.device.pk}/assign-branch/',
            {'branch_id': self.branch.pk, 'end_date': end_date.isoformat()},
            format='json',
        )

        self.assertEqual(response.status_code, 201, response.data)
        branch_period = DeviceCustomerAccessPeriod.objects.get(
            pk=response.data['access_period_id']
        )
        fallback_period = DeviceCustomerAccessPeriod.objects.get(
            device=self.device,
            reason='branch_assignment_end',
        )
        self.original_period.refresh_from_db()

        self.assertEqual(branch_period.branch_id, self.branch.pk)
        self.assertEqual(branch_period.organization_id, self.organization.pk)
        self.assertEqual(branch_period.subscription_id, self.subscription.pk)
        self.assertIsNotNone(branch_period.ended_at)
        self.assertIsNotNone(self.original_period.ended_at)
        self.assertEqual(
            fallback_period.started_at,
            timezone.make_aware(datetime.combine(
                end_date + timedelta(days=1),
                datetime_time.min,
            )),
        )

        now_period = active_customer_access_periods(
            organization_id=self.organization.pk,
            now=timezone.now(),
        ).get(device=self.device)
        self.assertEqual(now_period.branch_id, self.branch.pk)

        after_assignment = fallback_period.started_at + timedelta(seconds=1)
        organization_period = active_customer_access_periods(
            organization_id=self.organization.pk,
            now=after_assignment,
        ).get(device=self.device)
        self.assertIsNone(organization_period.branch_id)
        self.assertFalse(
            active_customer_access_periods(
                organization_id=self.organization.pk,
                branch_id=self.branch.pk,
                now=after_assignment,
            ).filter(device=self.device).exists()
        )

    def test_manager_can_assign_without_a_predefined_end_date(self):
        response = self.client.post(
            f'/api/devices/{self.device.pk}/assign-branch/',
            {'branch_id': self.branch.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 201, response.data)
        period = DeviceCustomerAccessPeriod.objects.get(
            pk=response.data['access_period_id']
        )
        self.assertEqual(period.branch_id, self.branch.pk)
        self.assertIsNone(period.ended_at)
        self.assertFalse(
            DeviceCustomerAccessPeriod.objects.filter(
                device=self.device,
                reason='branch_assignment_end',
            ).exists()
        )

    def test_manager_cannot_assign_device_to_another_organizations_branch(self):
        other_organization = Organization.objects.create(
            name='External Branch Assignment Org',
            code='EXTERNAL-BRANCH-ASSIGNMENT-ORG',
        )
        foreign_branch = Branch.objects.create(
            organization=other_organization,
            name='External Branch Assignment',
            code='EXTERNAL-BRANCH-ASSIGNMENT',
        )

        response = self.client.post(
            f'/api/devices/{self.device.pk}/assign-branch/',
            {'branch_id': foreign_branch.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(
            DeviceCustomerAccessPeriod.objects.filter(
                device=self.device,
                branch=foreign_branch,
            ).count(),
            0,
        )
        self.original_period.refresh_from_db()
        self.assertIsNone(self.original_period.ended_at)

    def test_manager_cannot_assign_a_device_that_already_has_a_branch(self):
        self.device.branch = self.branch
        self.device.save(update_fields=['branch'])

        response = self.client.post(
            f'/api/devices/{self.device.pk}/assign-branch/',
            {'branch_id': self.branch.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(
            DeviceCustomerAccessPeriod.objects.filter(
                device=self.device,
                branch=self.branch,
            ).count(),
            0,
        )

    def test_branch_manager_cannot_assign_device_to_branch(self):
        branch_manager = User.objects.create_user(
            username='branch_assignment_api_branch_manager',
            password='test-password',
            role='branch_manager',
            account_type='organization',
            organization=self.organization,
            branch=self.branch,
        )
        self.client.force_authenticate(user=branch_manager)

        response = self.client.post(
            f'/api/devices/{self.device.pk}/assign-branch/',
            {'branch_id': self.branch.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 403, response.data)
        self.assertTrue(
            DeviceCustomerAccessPeriod.objects.filter(
                pk=self.original_period.pk,
                ended_at__isnull=True,
            ).exists()
        )

    def test_personal_customer_cannot_assign_device_to_branch(self):
        personal_user = User.objects.create_user(
            username='branch_assignment_api_personal',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        self.client.force_authenticate(user=personal_user)

        response = self.client.post(
            f'/api/devices/{self.device.pk}/assign-branch/',
            {'branch_id': self.branch.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 403, response.data)
        self.assertTrue(
            DeviceCustomerAccessPeriod.objects.filter(
                pk=self.original_period.pk,
                ended_at__isnull=True,
            ).exists()
        )

    def test_assignment_rejects_malformed_and_past_end_dates(self):
        from datetime import timedelta

        invalid_dates = [
            'not-a-date',
            (timezone.localdate() - timedelta(days=1)).isoformat(),
        ]
        for end_date in invalid_dates:
            with self.subTest(end_date=end_date):
                response = self.client.post(
                    f'/api/devices/{self.device.pk}/assign-branch/',
                    {'branch_id': self.branch.pk, 'end_date': end_date},
                    format='json',
                )
                self.assertEqual(response.status_code, 400, response.data)
                self.assertTrue(
                    DeviceCustomerAccessPeriod.objects.filter(
                        pk=self.original_period.pk,
                        ended_at__isnull=True,
                    ).exists()
                )
                self.assertFalse(
                    DeviceCustomerAccessPeriod.objects.filter(
                        device=self.device,
                        branch=self.branch,
                    ).exists()
                )

    def test_assignment_rejects_end_date_after_contract_or_device_assignment(self):
        from datetime import timedelta

        too_late = max(self.subscription.end_date, self.link.end_date) + timedelta(days=1)
        response = self.client.post(
            f'/api/devices/{self.device.pk}/assign-branch/',
            {'branch_id': self.branch.pk, 'end_date': too_late.isoformat()},
            format='json',
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertTrue(
            DeviceCustomerAccessPeriod.objects.filter(
                pk=self.original_period.pk,
                ended_at__isnull=True,
            ).exists()
        )
        self.assertFalse(
            DeviceCustomerAccessPeriod.objects.filter(
                device=self.device,
                branch=self.branch,
            ).exists()
        )

    def test_assignment_rejects_suspended_or_expired_contract(self):
        for status in ('suspended', 'expired'):
            with self.subTest(subscription_status=status):
                self.subscription.status = status
                self.subscription.save(update_fields=['status'])

                response = self.client.post(
                    f'/api/devices/{self.device.pk}/assign-branch/',
                    {'branch_id': self.branch.pk},
                    format='json',
                )

                # Inactive contracts are excluded by DeviceViewSet.get_queryset(),
                # so the device is intentionally hidden before the action runs.
                self.assertEqual(response.status_code, 404, response.data)
                self.assertTrue(
                    DeviceCustomerAccessPeriod.objects.filter(
                        pk=self.original_period.pk,
                        ended_at__isnull=True,
                    ).exists()
                )
                self.assertFalse(
                    DeviceCustomerAccessPeriod.objects.filter(
                        device=self.device,
                        branch=self.branch,
                    ).exists()
                )
                self.subscription.status = 'active'
                self.subscription.save(update_fields=['status'])


class OrganizationDeviceBranchChangeApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        today = timezone.localdate()
        now = timezone.now()
        self.organization = Organization.objects.create(
            name='Branch Change API Organization',
            code='BRANCH-CHANGE-API-ORG',
        )
        self.manager = User.objects.create_user(
            username='branch_change_api_manager',
            password='test-password',
            role='main_user',
            account_type='organization',
            organization=self.organization,
        )
        self.old_branch = Branch.objects.create(
            organization=self.organization,
            name='Old Branch',
            code='BRANCH-CHANGE-OLD',
        )
        self.new_branch = Branch.objects.create(
            organization=self.organization,
            name='New Branch',
            code='BRANCH-CHANGE-NEW',
        )
        self.device = Device.objects.create(
            imei='860000000009972',
            organization=self.organization,
            management_status='installed',
        )
        self.subscription = Subscription.objects.create(
            contract_number='BRANCH-CHANGE-API-CONTRACT',
            customer_type='organization',
            organization=self.organization,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=30),
            status='active',
        )
        self.link = SubscriptionDevice.objects.create(
            subscription=self.subscription,
            device=self.device,
            start_date=self.subscription.start_date,
            end_date=self.subscription.end_date,
        )
        SubscriptionDevice.objects.filter(pk=self.link.pk).update(
            assigned_at=now - timedelta(days=3)
        )
        self.assignment_end = today + timedelta(days=5)
        self.old_period = DeviceCustomerAccessPeriod.objects.create(
            device=self.device,
            organization=self.organization,
            subscription=self.subscription,
            branch=self.old_branch,
            started_at=now - timedelta(days=2),
            ended_at=timezone.make_aware(
                __import__('datetime').datetime.combine(
                    self.assignment_end,
                    __import__('datetime').time.max,
                )
            ),
            reason='branch_assignment',
        )
        self.old_fallback = DeviceCustomerAccessPeriod.objects.create(
            device=self.device,
            organization=self.organization,
            subscription=self.subscription,
            branch=None,
            started_at=timezone.make_aware(
                __import__('datetime').datetime.combine(
                    self.assignment_end + timedelta(days=1),
                    __import__('datetime').time.min,
                )
            ),
            reason='branch_assignment_end',
        )
        self.client.force_authenticate(user=self.manager)

    def test_change_branch_preserves_existing_end_date_and_retires_old_fallback(self):
        response = self.client.post(
            f'/api/devices/{self.device.pk}/change-branch/',
            {'branch_id': self.new_branch.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.old_period.refresh_from_db()
        self.old_fallback.refresh_from_db()
        new_period = DeviceCustomerAccessPeriod.objects.get(
            pk=response.data['access_period_id']
        )
        new_fallback = DeviceCustomerAccessPeriod.objects.get(
            device=self.device,
            reason='branch_assignment_end',
            started_at__gt=timezone.now(),
            ended_at__isnull=True,
        )

        self.assertLessEqual(self.old_period.ended_at, timezone.now())
        self.assertEqual(self.old_fallback.ended_at, self.old_fallback.started_at)
        self.assertEqual(new_period.branch_id, self.new_branch.pk)
        self.assertEqual(
            timezone.localtime(new_period.ended_at).date(),
            self.assignment_end,
        )
        self.assertEqual(
            timezone.localtime(new_fallback.started_at).date(),
            self.assignment_end + timedelta(days=1),
        )
        self.assertTrue(
            active_customer_access_periods(
                organization_id=self.organization.pk,
                branch_id=self.new_branch.pk,
            ).filter(device=self.device).exists()
        )
        self.assertFalse(
            active_customer_access_periods(
                organization_id=self.organization.pk,
                branch_id=self.old_branch.pk,
            ).filter(device=self.device).exists()
        )

    def test_change_branch_replaces_end_date_when_new_date_is_supplied(self):
        new_end_date = timezone.localdate() + timedelta(days=8)
        response = self.client.post(
            f'/api/devices/{self.device.pk}/change-branch/',
            {
                'branch_id': self.new_branch.pk,
                'end_date': new_end_date.isoformat(),
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201, response.data)
        new_period = DeviceCustomerAccessPeriod.objects.get(
            pk=response.data['access_period_id']
        )
        self.assertEqual(
            timezone.localtime(new_period.ended_at).date(),
            new_end_date,
        )

    def test_clearing_branch_restores_main_user_access_immediately(self):
        response = self.client.post(
            f'/api/devices/{self.device.pk}/change-branch/',
            {'branch_id': None},
            format='json',
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.old_period.refresh_from_db()
        self.old_fallback.refresh_from_db()
        new_period = DeviceCustomerAccessPeriod.objects.get(
            pk=response.data['access_period_id']
        )

        self.assertLessEqual(self.old_period.ended_at, timezone.now())
        self.assertEqual(self.old_fallback.ended_at, self.old_fallback.started_at)
        self.assertIsNone(new_period.branch_id)
        self.assertIsNone(new_period.ended_at)
        self.assertTrue(
            active_customer_access_periods(
                organization_id=self.organization.pk,
            ).filter(device=self.device).exists()
        )
        self.assertFalse(
            active_customer_access_periods(
                organization_id=self.organization.pk,
                branch_id=self.old_branch.pk,
            ).filter(device=self.device).exists()
        )

    def test_change_branch_rejects_branch_from_another_organization(self):
        foreign_organization = Organization.objects.create(
            name='Foreign Branch Change Organization',
            code='FOREIGN-BRANCH-CHANGE-ORG',
        )
        foreign_branch = Branch.objects.create(
            organization=foreign_organization,
            name='Foreign Branch',
            code='FOREIGN-BRANCH-CHANGE',
        )

        response = self.client.post(
            f'/api/devices/{self.device.pk}/change-branch/',
            {'branch_id': foreign_branch.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.old_period.refresh_from_db()
        self.assertGreater(self.old_period.ended_at, timezone.now())
        self.assertFalse(
            DeviceCustomerAccessPeriod.objects.filter(
                device=self.device,
                branch=foreign_branch,
            ).exists()
        )

    def test_branch_manager_cannot_change_or_clear_branch_assignment(self):
        branch_manager = User.objects.create_user(
            username='branch_change_api_branch_manager',
            password='test-password',
            role='branch_manager',
            account_type='organization',
            organization=self.organization,
            branch=self.old_branch,
        )
        self.client.force_authenticate(user=branch_manager)

        response = self.client.post(
            f'/api/devices/{self.device.pk}/change-branch/',
            {'branch_id': None},
            format='json',
        )

        self.assertEqual(response.status_code, 403, response.data)
        self.old_period.refresh_from_db()
        self.assertGreater(self.old_period.ended_at, timezone.now())
