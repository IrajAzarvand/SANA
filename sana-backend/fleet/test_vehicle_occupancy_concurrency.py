import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch

from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import User
from fleet import device_operations
from fleet.models import Device, Vehicle
from organizations.models import Organization, Subscription, SubscriptionDevice


class VehicleOccupancyConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.organization = Organization.objects.create(
            name='Vehicle Lock Organization',
            code='VEHICLE-LOCK-ORG',
        )
        today = timezone.localdate()
        self.subscription = Subscription.objects.create(
            contract_number='VEHICLE-LOCK-CONTRACT',
            customer_type='organization',
            organization=self.organization,
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=30),
            status='active',
        )
        self.admin = User.objects.create_user(
            username='vehicle-lock-admin',
            password='test-password',
            role='site_admin',
            account_type='admin',
            is_staff=True,
            is_superuser=True,
        )
        self.vehicle = Vehicle.objects.create(
            organization=self.organization,
            plate='33ج333',
        )
        self.devices = []
        for index in (1, 2):
            device = Device.objects.create(
                imei=f'86000000000800{index}',
                organization=self.organization,
                current_holder_organization=self.organization,
                management_status='installed',
            )
            SubscriptionDevice.objects.create(
                subscription=self.subscription,
                device=device,
                start_date=self.subscription.start_date,
                end_date=self.subscription.end_date,
            )
            self.devices.append(device)

    def test_only_one_concurrent_transfer_can_claim_the_same_vehicle(self):
        if not connection.features.has_select_for_update:
            self.skipTest('The database backend does not support SELECT FOR UPDATE.')

        first_checked_vehicle = threading.Event()
        release_first_operation = threading.Event()
        second_reached_availability_check = threading.Event()
        original_check = device_operations._ensure_vehicle_available

        def controlled_check(vehicle, **kwargs):
            original_check(vehicle, **kwargs)
            thread_name = threading.current_thread().name
            if thread_name.endswith('_0'):
                first_checked_vehicle.set()
                if not release_first_operation.wait(timeout=10):
                    raise AssertionError('Timed out waiting to release the first vehicle claim.')
            elif thread_name.endswith('_1'):
                second_reached_availability_check.set()

        def claim_device(device_id):
            close_old_connections()
            try:
                device = Device.objects.get(pk=device_id)
                vehicle = Vehicle.objects.get(pk=self.vehicle.pk)
                return device_operations.execute_device_operation(
                    device=device,
                    operation_type='transfer_vehicle',
                    performed_by=self.admin,
                    subscription=self.subscription,
                    target_vehicle=vehicle,
                    reason='concurrent claim test',
                )
            finally:
                close_old_connections()

        with patch.object(device_operations, '_ensure_vehicle_available', side_effect=controlled_check):
            with ThreadPoolExecutor(max_workers=2, thread_name_prefix='vehicle-claim') as pool:
                first = pool.submit(claim_device, self.devices[0].pk)
                self.assertTrue(first_checked_vehicle.wait(timeout=5))

                second = pool.submit(claim_device, self.devices[1].pk)
                # The second operation must be blocked on the Vehicle row lock,
                # so it cannot reach the occupancy query while the first holds it.
                self.assertFalse(second_reached_availability_check.wait(timeout=0.5))

                release_first_operation.set()
                first_result = first.result(timeout=10)
                with self.assertRaises(ValidationError):
                    second.result(timeout=10)

        assigned_devices = Device.objects.filter(vehicle=self.vehicle)
        self.assertEqual(assigned_devices.count(), 1)
        self.assertEqual(assigned_devices.get().pk, self.devices[0].pk)
