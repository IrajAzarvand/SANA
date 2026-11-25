from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from fleet.models import Device, DeviceCustomerAccessPeriod, DeviceOwnershipHistory
from organizations.models import Organization, Subscription, SubscriptionDevice


class ContractIntegrityDatabaseConstraintTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name='Integrity Constraint Org',
            code='INTEGRITY-CONSTRAINT-ORG',
        )
        self.other_organization = Organization.objects.create(
            name='Integrity Other Org',
            code='INTEGRITY-CONSTRAINT-OTHER',
        )
        today = timezone.localdate()
        self.subscription = Subscription.objects.create(
            contract_number='INTEGRITY-CONTRACT-ONE',
            customer_type='organization',
            organization=self.organization,
            start_date=today,
            end_date=today + timedelta(days=30),
            status='active',
        )
        self.other_subscription = Subscription.objects.create(
            contract_number='INTEGRITY-CONTRACT-TWO',
            customer_type='organization',
            organization=self.organization,
            start_date=today,
            end_date=today + timedelta(days=30),
            status='active',
        )
        self.device = Device.objects.create(imei='860000000000955')
        self.personal_user = User.objects.create_user(
            username='integrity-personal-user',
            password='test-password',
            account_type='personal',
            role='personal_user',
        )

    def assert_database_rejects(self, operation):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                operation()

    def test_subscription_requires_exact_customer_type_shape(self):
        today = timezone.localdate()
        self.assert_database_rejects(lambda: Subscription.objects.create(
            contract_number='INTEGRITY-BAD-CUSTOMER',
            customer_type='personal',
            organization=self.organization,
            user=None,
            start_date=today,
            end_date=today + timedelta(days=1),
        ))

    def test_subscription_and_device_link_dates_cannot_be_reversed(self):
        today = timezone.localdate()
        self.assert_database_rejects(lambda: Subscription.objects.create(
            contract_number='INTEGRITY-REVERSED-CONTRACT',
            customer_type='organization',
            organization=self.organization,
            start_date=today + timedelta(days=1),
            end_date=today,
        ))
        self.assert_database_rejects(lambda: SubscriptionDevice.objects.create(
            subscription=self.subscription,
            device=Device.objects.create(imei='860000000000956'),
            start_date=today + timedelta(days=1),
            end_date=today,
        ))

    def test_device_owner_and_holder_fields_must_each_have_one_identity(self):
        self.assert_database_rejects(lambda: Device.objects.create(
            imei='860000000000957',
            organization=self.organization,
            owner_user=self.personal_user,
        ))
        self.assert_database_rejects(lambda: Device.objects.create(
            imei='860000000000958',
            current_holder_organization=self.organization,
            current_holder_user=self.personal_user,
        ))

    def test_device_cannot_have_two_open_ownership_periods(self):
        DeviceOwnershipHistory.objects.create(
            device=self.device,
            organization=self.organization,
        )
        self.assert_database_rejects(lambda: DeviceOwnershipHistory.objects.create(
            device=self.device,
            organization=self.other_organization,
        ))

    def test_access_and_ownership_period_dates_cannot_be_reversed(self):
        now = timezone.now()
        self.assert_database_rejects(lambda: DeviceCustomerAccessPeriod.objects.create(
            device=Device.objects.create(imei='860000000000959'),
            organization=self.organization,
            started_at=now,
            ended_at=now - timedelta(seconds=1),
        ))
        self.assert_database_rejects(lambda: DeviceOwnershipHistory.objects.create(
            device=Device.objects.create(imei='860000000000960'),
            organization=self.organization,
            started_at=now,
            ended_at=now - timedelta(seconds=1),
        ))

    def test_device_api_cannot_change_legal_owner_without_lifecycle_transfer(self):
        from fleet.serializers import DeviceSerializer

        device = Device.objects.create(
            imei='860000000000970',
            organization=self.organization,
        )
        serializer = DeviceSerializer(
            instance=device,
            data={'organization': self.other_organization.id},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('organization', serializer.errors)

    def test_device_creation_cannot_preassign_holder_branch_or_vehicle(self):
        from fleet.models import Vehicle
        from fleet.serializers import DeviceSerializer
        from organizations.models import Branch

        branch = Branch.objects.create(
            organization=self.organization,
            name='Protected Assignment Branch',
            code='PROTECTED-ASSIGNMENT-BRANCH',
        )
        vehicle = Vehicle.objects.create(
            plate='88ب888',
            organization=self.organization,
            branch=branch,
        )
        invalid_assignments = (
            ('current_holder_organization', self.organization.id, '860000000000971'),
            ('branch', branch.id, '860000000000976'),
            ('vehicle', vehicle.id, '860000000000977'),
        )
        for field_name, value, imei in invalid_assignments:
            serializer = DeviceSerializer(data={
                'imei': imei,
                'organization': self.organization.id,
                field_name: value,
            })
            self.assertFalse(serializer.is_valid())
            self.assertIn(field_name, serializer.errors)

    def test_device_creation_records_initial_legal_ownership_history(self):
        from fleet.serializers import DeviceSerializer

        serializer = DeviceSerializer(data={
            'imei': '860000000000972',
            'organization': self.organization.id,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        device = serializer.save()

        ownership = DeviceOwnershipHistory.objects.get(
            device=device,
            ended_at__isnull=True,
        )
        self.assertEqual(ownership.organization_id, self.organization.id)
        self.assertIsNone(ownership.owner_user_id)


    def test_contract_assignment_preserves_legal_owner_and_sets_current_holder(self):
        from organizations.serializers import SubscriptionDeviceSerializer

        device = Device.objects.create(
            imei='860000000000973',
            owner_user=self.personal_user,
        )
        serializer = SubscriptionDeviceSerializer(data={
            'subscription': self.subscription.id,
            'device': device.id,
            'start_date': self.subscription.start_date,
            'end_date': self.subscription.end_date,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        device.refresh_from_db()
        self.assertEqual(device.owner_user_id, self.personal_user.id)
        self.assertIsNone(device.organization_id)
        self.assertEqual(device.current_holder_organization_id, self.organization.id)
        self.assertIsNone(device.current_holder_user_id)
        access = DeviceCustomerAccessPeriod.objects.get(
            device=device,
            ended_at__isnull=True,
        )
        self.assertEqual(access.organization_id, self.organization.id)
        self.assertIsNone(access.user_id)

    def test_returned_lifecycle_event_does_not_erase_legal_owner(self):
        from fleet.lifecycle import record_device_lifecycle_event

        device = Device.objects.create(
            imei='860000000000974',
            organization=self.organization,
            current_holder_organization=self.other_organization,
            management_status='installed',
        )
        record_device_lifecycle_event(
            device=device,
            event_type='returned',
            organization=self.other_organization,
            user=None,
        )

        device.refresh_from_db()
        self.assertEqual(device.organization_id, self.organization.id)
        self.assertIsNone(device.current_holder_organization_id)
        self.assertIsNone(device.current_holder_user_id)
        self.assertIsNone(device.branch_id)
        self.assertIsNone(device.vehicle_id)

    def test_repaired_lifecycle_event_marks_device_ready_for_disposition(self):
        from fleet.lifecycle import record_device_lifecycle_event

        device = Device.objects.create(
            imei='860000000000975',
            management_status='in_repair',
        )
        record_device_lifecycle_event(device=device, event_type='repaired')

        device.refresh_from_db()
        self.assertEqual(device.management_status, 'ready')


    def test_new_contract_link_cannot_implicitly_close_another_contract(self):
        from django.core.exceptions import ValidationError

        first_link = SubscriptionDevice.objects.create(
            subscription=self.subscription,
            device=self.device,
            start_date=self.subscription.start_date,
            end_date=self.subscription.end_date,
        )
        with self.assertRaises(ValidationError):
            SubscriptionDevice.objects.create(
                subscription=self.other_subscription,
                device=self.device,
                start_date=self.other_subscription.start_date,
                end_date=self.other_subscription.end_date,
            )

        first_link.refresh_from_db()
        self.assertIsNone(first_link.unassigned_at)


    def test_device_assignment_dates_do_not_recalculate_legal_contract_dates(self):
        original_contract_end = self.subscription.end_date
        link_end = self.subscription.start_date + timedelta(days=5)
        SubscriptionDevice.objects.create(
            subscription=self.subscription,
            device=self.device,
            start_date=self.subscription.start_date,
            end_date=link_end,
        )

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.end_date, original_contract_end)


    def test_temporary_replacement_returns_to_warehouse_when_original_returns(self):
        from fleet.device_operations import execute_device_operation
        from fleet.models import DeviceReplacementRelation, Vehicle
        from organizations.models import Branch

        branch = Branch.objects.create(
            organization=self.organization,
            name='Temporary Loaner Branch',
            code='TEMP-LOANER-BRANCH',
        )
        vehicle = Vehicle.objects.create(
            plate='99ج999',
            organization=self.organization,
            branch=branch,
        )
        source = Device.objects.create(
            imei='860000000000979',
            organization=self.other_organization,
            current_holder_organization=self.organization,
            branch=branch,
            vehicle=vehicle,
            management_status='installed',
        )
        SubscriptionDevice.objects.create(
            subscription=self.subscription,
            device=source,
            start_date=self.subscription.start_date,
            end_date=self.subscription.end_date,
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=source,
            organization=self.organization,
            branch=branch,
            subscription=self.subscription,
            started_at=timezone.now() - timedelta(minutes=2),
        )
        loaner = Device.objects.create(
            imei='860000000000980',
            organization=self.other_organization,
            management_status='warehouse',
        )

        execute_device_operation(
            device=source,
            operation_type='return_for_repair',
            performed_by=None,
            replacement_device=loaner,
            subscription=self.subscription,
            replacement_type='temporary_repair',
            replacement_method='warranty',
        )
        execute_device_operation(
            device=source,
            operation_type='repaired',
            performed_by=None,
        )
        execute_device_operation(
            device=source,
            operation_type='disposition',
            performed_by=None,
            outcome_action='return_customer_no_vehicle',
        )

        source.refresh_from_db()
        loaner.refresh_from_db()
        relation = DeviceReplacementRelation.objects.get(
            source_device=source,
            replacement_device=loaner,
        )
        self.assertIsNotNone(relation.returned_at)
        self.assertEqual(source.current_holder_organization_id, self.organization.id)
        self.assertTrue(DeviceCustomerAccessPeriod.objects.filter(
            device=source,
            organization=self.organization,
            ended_at__isnull=True,
        ).exists())
        self.assertEqual(loaner.management_status, 'warehouse')
        self.assertEqual(loaner.organization_id, self.other_organization.id)
        self.assertIsNone(loaner.current_holder_organization_id)
        self.assertIsNone(loaner.active_subscription_link)
        self.assertFalse(DeviceCustomerAccessPeriod.objects.filter(
            device=loaner,
            ended_at__isnull=True,
        ).exists())

    def test_future_contract_assignment_is_recorded_but_access_starts_on_contract_date(self):
        from fleet.customer_access import active_customer_access_periods
        from organizations.serializers import SubscriptionDeviceSerializer

        today = timezone.localdate()
        future_start = today + timedelta(days=2)
        future_end = today + timedelta(days=30)
        subscription = Subscription.objects.create(
            contract_number='INTEGRITY-FUTURE-CONTRACT',
            customer_type='personal',
            user=self.personal_user,
            start_date=future_start,
            end_date=future_end,
            status='active',
        )
        device = Device.objects.create(
            imei='860000000000978',
            owner_user=self.personal_user,
        )
        serializer = SubscriptionDeviceSerializer(data={
            'subscription': subscription.id,
            'device': device.id,
            'start_date': future_start,
            'end_date': future_end,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        link = serializer.save()

        self.assertTrue(
            DeviceCustomerAccessPeriod.objects.filter(
                device=device,
                subscription=subscription,
                ended_at__isnull=True,
            ).exists()
        )
        self.assertFalse(
            active_customer_access_periods(user_id=self.personal_user.id)
            .filter(device=device)
            .exists()
        )

        subscription.start_date = today
        subscription.save(update_fields=['start_date'])
        link.start_date = today
        link.save(update_fields=['start_date'])

        self.assertTrue(
            active_customer_access_periods(user_id=self.personal_user.id)
            .filter(device=device)
            .exists()
        )
