from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from fleet.models import Device, DeviceCustomerAccessPeriod
from organizations.models import Branch, Organization, Subscription, SubscriptionDevice


class ContractBackedDeviceAccessTests(TestCase):
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
