from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from fleet.models import Device, DeviceCustomerAccessPeriod, DeviceOperation, Vehicle
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
            branch=None,
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

    def test_customer_transfer_keeps_device_unbranched_until_separate_assignment(self):
        response = self.admin_client.post(
            '/api/device-operations/',
            {
                'device': self.device.pk,
                'operation_type': 'transfer_customer',
                'target_organization': self.target_organization.pk,
                'target_subscription': self.target_subscription.pk,
                'target_vehicle': self.target_vehicle.pk,
                'reason': 'transfer test',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.device.refresh_from_db()
        self.assertEqual(self.device.organization_id, self.target_organization.pk)
        self.assertIsNone(self.device.branch_id)
        self.assertEqual(self.device.vehicle_id, self.target_vehicle.pk)
        self.assertTrue(
            DeviceCustomerAccessPeriod.objects.filter(
                device=self.device,
                organization=self.target_organization,
                branch__isnull=True,
                subscription=self.target_subscription,
                ended_at__isnull=True,
            ).exists()
        )

        branch_client = APIClient()
        branch_client.force_authenticate(user=self.target_branch_manager)
        devices_response = branch_client.get('/api/devices/')

        self.assertEqual(devices_response.status_code, 200, devices_response.data)
        rows = (
            devices_response.data['results']
            if isinstance(devices_response.data, dict) and 'results' in devices_response.data
            else devices_response.data
        )
        self.assertNotIn(self.device.pk, [row['id'] for row in rows])

    def test_customer_transfer_rejects_branched_target_vehicle_without_mutation(self):
        branched_target_vehicle = Vehicle.objects.create(
            organization=self.target_organization,
            branch=self.target_branch,
            plate='22ب223',
        )
        initial_operation_count = DeviceOperation.objects.count()

        response = self.admin_client.post(
            '/api/device-operations/',
            {
                'device': self.device.pk,
                'operation_type': 'transfer_customer',
                'target_organization': self.target_organization.pk,
                'target_subscription': self.target_subscription.pk,
                'target_vehicle': branched_target_vehicle.pk,
                'reason': 'branched target vehicle rejection test',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.device.refresh_from_db()
        self.assertEqual(self.device.organization_id, self.source_organization.pk)
        self.assertEqual(
            self.device.current_holder_organization_id,
            self.source_organization.pk,
        )
        self.assertEqual(self.device.branch_id, self.source_branch.pk)
        self.assertEqual(self.device.vehicle_id, self.source_vehicle.pk)
        self.assertTrue(
            SubscriptionDevice.objects.filter(
                device=self.device,
                subscription=self.source_subscription,
                unassigned_at__isnull=True,
            ).exists()
        )
        self.assertTrue(
            DeviceCustomerAccessPeriod.objects.filter(
                device=self.device,
                subscription=self.source_subscription,
                branch=self.source_branch,
                ended_at__isnull=True,
            ).exists()
        )
        self.assertFalse(
            SubscriptionDevice.objects.filter(
                device=self.device,
                subscription=self.target_subscription,
                unassigned_at__isnull=True,
            ).exists()
        )
        self.assertEqual(DeviceOperation.objects.count(), initial_operation_count)

    def test_customer_transfer_rejects_devices_in_blocked_operational_statuses_without_mutation(self):
        blocked_statuses = (
            'faulty',
            'in_repair',
            'ready',
            'lost',
            'stolen',
            'unusable',
            'disposed',
        )
        initial_operation_count = DeviceOperation.objects.count()

        for status in blocked_statuses:
            with self.subTest(status=status):
                Device.objects.filter(pk=self.device.pk).update(management_status=status)

                response = self.admin_client.post(
                    '/api/device-operations/',
                    {
                        'device': self.device.pk,
                        'operation_type': 'transfer_customer',
                        'target_organization': self.target_organization.pk,
                        'target_subscription': self.target_subscription.pk,
                        'target_vehicle': self.target_vehicle.pk,
                        'reason': 'blocked status transfer test',
                    },
                    format='json',
                )

                self.assertEqual(response.status_code, 400, response.data)
                self.device.refresh_from_db()
                self.assertEqual(self.device.management_status, status)
                self.assertEqual(self.device.organization_id, self.source_organization.pk)
                self.assertEqual(
                    self.device.current_holder_organization_id,
                    self.source_organization.pk,
                )
                self.assertEqual(self.device.branch_id, self.source_branch.pk)
                self.assertEqual(self.device.vehicle_id, self.source_vehicle.pk)
                self.assertTrue(
                    SubscriptionDevice.objects.filter(
                        device=self.device,
                        subscription=self.source_subscription,
                        unassigned_at__isnull=True,
                    ).exists()
                )
                self.assertTrue(
                    DeviceCustomerAccessPeriod.objects.filter(
                        device=self.device,
                        subscription=self.source_subscription,
                        ended_at__isnull=True,
                    ).exists()
                )
                self.assertEqual(DeviceOperation.objects.count(), initial_operation_count)

