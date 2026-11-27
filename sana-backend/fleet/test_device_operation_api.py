from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from fleet.models import Device, DeviceCustomerAccessPeriod, Vehicle
from organizations.models import Branch, Organization, Subscription, SubscriptionDevice


class DeviceOperationCustomerTransferApiTests(TestCase):
    def setUp(self):
        self.source_organization = Organization.objects.create(
            name='Transfer Source Organization',
            code='TRANSFER-SOURCE-ORG',
        )
        self.target_organization = Organization.objects.create(
            name='Transfer Target Organization',
            code='TRANSFER-TARGET-ORG',
        )
        self.source_branch = Branch.objects.create(
            organization=self.source_organization,
            name='Source Branch',
            code='TRANSFER-SOURCE-BR',
            status='active',
        )
        self.target_branch = Branch.objects.create(
            organization=self.target_organization,
            name='Target Branch',
            code='TRANSFER-TARGET-BR',
            status='active',
        )
        self.source_vehicle = Vehicle.objects.create(
            organization=self.source_organization,
            branch=self.source_branch,
            plate='11الف111',
        )
        self.target_vehicle = Vehicle.objects.create(
            organization=self.target_organization,
            branch=self.target_branch,
            plate='22ب222',
        )
        self.site_admin = User.objects.create_user(
            username='device-transfer-site-admin',
            password='test-password',
            role='site_admin',
            account_type='admin',
            is_staff=True,
            is_superuser=True,
        )
        self.target_branch_manager = User.objects.create_user(
            username='device-transfer-target-branch-manager',
            password='test-password',
            role='branch_manager',
            account_type='organization',
            organization=self.target_organization,
            branch=self.target_branch,
        )
        today = timezone.localdate()
        now = timezone.now()
        self.source_subscription = Subscription.objects.create(
            contract_number='TRANSFER-SOURCE-CONTRACT',
            customer_type='organization',
            organization=self.source_organization,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=30),
            status='active',
        )
        self.target_subscription = Subscription.objects.create(
            contract_number='TRANSFER-TARGET-CONTRACT',
            customer_type='organization',
            organization=self.target_organization,
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=30),
            status='active',
        )
        self.device = Device.objects.create(
            imei='860000000007771',
            organization=self.source_organization,
            branch=self.source_branch,
            current_holder_organization=self.source_organization,
            vehicle=self.source_vehicle,
            management_status='installed',
        )
        source_link = SubscriptionDevice.objects.create(
            subscription=self.source_subscription,
            device=self.device,
            start_date=self.source_subscription.start_date,
            end_date=self.source_subscription.end_date,
        )
        SubscriptionDevice.objects.filter(pk=source_link.pk).update(
            assigned_at=now - timedelta(minutes=5),
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=self.device,
            organization=self.source_organization,
            subscription=self.source_subscription,
            branch=self.source_branch,
            started_at=now - timedelta(minutes=5),
        )
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(user=self.site_admin)

    def test_customer_transfer_applies_target_branch_and_vehicle(self):
        response = self.admin_client.post(
            '/api/device-operations/',
            {
                'device': self.device.pk,
                'operation_type': 'transfer_customer',
                'target_organization': self.target_organization.pk,
                'target_subscription': self.target_subscription.pk,
                'target_branch': self.target_branch.pk,
                'target_vehicle': self.target_vehicle.pk,
                'reason': 'customer transfer regression test',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.device.refresh_from_db()
        self.assertEqual(self.device.organization_id, self.target_organization.pk)
        self.assertEqual(self.device.branch_id, self.target_branch.pk)
        self.assertEqual(self.device.vehicle_id, self.target_vehicle.pk)
        self.assertTrue(
            DeviceCustomerAccessPeriod.objects.filter(
                device=self.device,
                organization=self.target_organization,
                branch=self.target_branch,
                subscription=self.target_subscription,
                ended_at__isnull=True,
            ).exists()
        )

        branch_client = APIClient()
        branch_client.force_authenticate(user=self.target_branch_manager)
        devices_response = branch_client.get('/api/devices/')

        self.assertEqual(devices_response.status_code, 200, devices_response.data)
        rows = devices_response.data.get('results', devices_response.data)
        transferred = next(row for row in rows if row['id'] == self.device.pk)
        self.assertEqual(transferred['branch_name'], self.target_branch.name)
        self.assertEqual(transferred['vehicle_plate'], self.target_vehicle.plate)
