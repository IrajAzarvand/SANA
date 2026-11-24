from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

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

    def test_device_link_dates_never_rewrite_parent_contract_dates(self):
        original_start = self.subscription.start_date
        original_end = self.subscription.end_date
        link = SubscriptionDevice.objects.create(
            subscription=self.subscription,
            device=self.device,
            start_date=original_start,
            end_date=original_end - timedelta(days=10),
        )
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.start_date, original_start)
        self.assertEqual(self.subscription.end_date, original_end)

        link.end_date = original_end + timedelta(days=30)
        link.save(update_fields=['end_date'])
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.start_date, original_start)
        self.assertEqual(self.subscription.end_date, original_end)

    def test_device_cannot_have_two_active_contract_links(self):
        SubscriptionDevice.objects.create(
            subscription=self.subscription,
            device=self.device,
            start_date=self.subscription.start_date,
            end_date=self.subscription.end_date,
        )
        self.assert_database_rejects(lambda: SubscriptionDevice.objects.bulk_create([
            SubscriptionDevice(
                subscription=self.other_subscription,
                device=self.device,
                start_date=self.other_subscription.start_date,
                end_date=self.other_subscription.end_date,
            )
        ]))

    def test_device_cannot_have_two_open_customer_access_periods(self):
        DeviceCustomerAccessPeriod.objects.create(
            device=self.device,
            organization=self.organization,
            subscription=self.subscription,
        )
        self.assert_database_rejects(lambda: DeviceCustomerAccessPeriod.objects.create(
            device=self.device,
            organization=self.other_organization,
            subscription=self.other_subscription,
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

    def test_ownership_history_defaults_to_legal_owner_not_current_holder(self):
        from fleet.device_operations import _open_ownership

        device = Device.objects.create(
            imei='860000000000980',
            organization=self.organization,
            current_holder_organization=self.other_organization,
            management_status='installed',
        )
        period = _open_ownership(device)
        self.assertIsNotNone(period)
        self.assertEqual(period.organization_id, self.organization.id)
        self.assertNotEqual(period.organization_id, self.other_organization.id)

    def test_device_cannot_have_both_legal_owner_types(self):
        from accounts.models import User

        user = User.objects.create_user(username='integrity_owner_user', password='test-password')
        self.assert_database_rejects(lambda: Device.objects.create(
            imei='860000000000956',
            organization=self.organization,
            owner_user=user,
        ))

    def test_device_serializer_cannot_bypass_audited_relationship_transfer(self):
        from fleet.serializers import DeviceSerializer

        device = Device.objects.create(
            imei='860000000000981',
            organization=self.organization,
            current_holder_organization=self.organization,
            management_status='installed',
        )
        serializer = DeviceSerializer(
            instance=device,
            data={'current_holder_organization': self.other_organization.id},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('current_holder_organization', serializer.errors)

    def test_device_serializer_cannot_create_preassigned_customer_or_branch(self):
        from fleet.serializers import DeviceSerializer

        serializer = DeviceSerializer(data={
            'imei': '860000000000982',
            'current_holder_organization': self.organization.id,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('current_holder_organization', serializer.errors)

    def test_device_cannot_have_both_current_holder_types(self):
        from accounts.models import User

        user = User.objects.create_user(username='integrity_holder_user', password='test-password')
        self.assert_database_rejects(lambda: Device.objects.create(
            imei='860000000000957',
            current_holder_organization=self.organization,
            current_holder_user=user,
        ))

    def test_permanent_replacement_inherits_legal_owner_and_customer_holder_separately(self):
        from datetime import timedelta
        from django.utils import timezone
        from fleet.device_operations import execute_device_operation
        from fleet.models import Vehicle
        from organizations.models import Branch

        today = timezone.localdate()
        legal_owner = Organization.objects.create(name='Replacement Legal Owner', code='REPL-LEGAL-OWNER')
        customer = Organization.objects.create(name='Replacement Customer', code='REPL-CUSTOMER')
        branch = Branch.objects.create(organization=customer, name='Replacement Branch', code='REPL-BRANCH')
        vehicle = Vehicle.objects.create(plate='66الف666', organization=customer, branch=branch)
        subscription = Subscription.objects.create(
            contract_number='REPL-OWNER-HOLDER-CONTRACT',
            customer_type='organization', organization=customer,
            start_date=today, end_date=today + timedelta(days=30), status='active',
        )
        source = Device.objects.create(
            imei='860000000000958', organization=legal_owner,
            current_holder_organization=customer, branch=branch, vehicle=vehicle,
            management_status='installed',
        )
        SubscriptionDevice.objects.create(
            subscription=subscription, device=source,
            start_date=subscription.start_date, end_date=subscription.end_date,
        )
        replacement = Device.objects.create(
            imei='860000000000959', management_status='warehouse',
        )

        execute_device_operation(
            device=source,
            operation_type='lost',
            performed_by=None,
            replacement_device=replacement,
            subscription=subscription,
            replacement_type='permanent_replacement',
            replacement_method='warranty',
        )

        replacement.refresh_from_db()
        source.refresh_from_db()
        self.assertEqual(replacement.organization_id, legal_owner.id)
        self.assertIsNone(replacement.owner_user_id)
        self.assertEqual(replacement.current_holder_organization_id, customer.id)
        self.assertIsNone(source.active_subscription_link)
        self.assertFalse(DeviceCustomerAccessPeriod.objects.filter(device=source, ended_at__isnull=True).exists())
        access = DeviceCustomerAccessPeriod.objects.get(device=replacement, ended_at__isnull=True)
        self.assertEqual(access.organization_id, customer.id)
        self.assertEqual(access.subscription_id, subscription.id)

    def test_repair_and_return_to_customer_reopen_access_without_erasing_history(self):
        from datetime import timedelta
        from django.utils import timezone
        from fleet.device_operations import execute_device_operation
        from organizations.models import Branch

        today = timezone.localdate()
        legal_owner = Organization.objects.create(name='Repair Legal Owner', code='REPAIR-LEGAL-OWNER')
        customer = Organization.objects.create(name='Repair Customer', code='REPAIR-CUSTOMER')
        branch = Branch.objects.create(organization=customer, name='Repair Branch', code='REPAIR-BRANCH')
        subscription = Subscription.objects.create(
            contract_number='REPAIR-ACCESS-CONTRACT',
            customer_type='organization', organization=customer,
            start_date=today, end_date=today + timedelta(days=30), status='active',
        )
        device = Device.objects.create(
            imei='860000000000960', organization=legal_owner,
            current_holder_organization=customer, branch=branch,
            management_status='installed',
        )
        SubscriptionDevice.objects.create(
            subscription=subscription, device=device,
            start_date=subscription.start_date, end_date=subscription.end_date,
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device, organization=customer, branch=branch, subscription=subscription,
        )

        execute_device_operation(device=device, operation_type='return_for_repair', performed_by=None)
        execute_device_operation(device=device, operation_type='repaired', performed_by=None)
        device.refresh_from_db()
        self.assertEqual(device.management_status, 'ready')
        execute_device_operation(
            device=device, operation_type='disposition', performed_by=None,
            outcome_action='return_customer_no_vehicle',
        )

        device.refresh_from_db()
        self.assertEqual(device.current_holder_organization_id, customer.id)
        self.assertIsNone(device.current_holder_user_id)
        self.assertTrue(DeviceCustomerAccessPeriod.objects.filter(
            device=device, organization=customer, ended_at__isnull=True,
        ).exists())
        # The original access period is closed and retained; the return
        # creates a new open period without manufacturing repair-time access.
        self.assertGreaterEqual(DeviceCustomerAccessPeriod.objects.filter(
            device=device, ended_at__isnull=False,
        ).count(), 1)

    def test_personal_customer_lifecycle_keeps_legal_owner_separate(self):
        from datetime import timedelta
        from accounts.models import User
        from fleet.device_operations import execute_device_operation
        from fleet.models import DeviceLifecycleEvent

        today = timezone.localdate()
        personal_customer = User.objects.create_user(
            username='personal-repair-customer',
            password='test-password',
            account_type='personal',
            role='personal_user',
        )
        subscription = Subscription.objects.create(
            contract_number='PERSONAL-REPAIR-CONTRACT',
            customer_type='personal',
            user=personal_customer,
            start_date=today,
            end_date=today + timedelta(days=30),
            status='active',
        )
        device = Device.objects.create(
            imei='860000000000979',
            organization=self.organization,
            current_holder_user=personal_customer,
            management_status='installed',
        )
        SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            user=personal_customer,
            subscription=subscription,
        )

        execute_device_operation(
            device=device,
            operation_type='return_for_repair',
            performed_by=None,
        )
        sent_event = DeviceLifecycleEvent.objects.get(
            device=device,
            event_type='sent_to_repair',
        )
        self.assertIsNone(sent_event.organization_id)
        self.assertEqual(sent_event.user_id, personal_customer.id)

        execute_device_operation(device=device, operation_type='repaired', performed_by=None)
        execute_device_operation(
            device=device,
            operation_type='disposition',
            performed_by=None,
            outcome_action='return_customer_no_vehicle',
        )
        device.refresh_from_db()
        self.assertEqual(device.organization_id, self.organization.id)
        self.assertIsNone(device.current_holder_organization_id)
        self.assertEqual(device.current_holder_user_id, personal_customer.id)
        current_access = DeviceCustomerAccessPeriod.objects.get(
            device=device,
            ended_at__isnull=True,
        )
        self.assertIsNone(current_access.organization_id)
        self.assertEqual(current_access.user_id, personal_customer.id)

    def test_branch_transfer_uses_contract_customer_not_legal_owner(self):
        from datetime import timedelta
        from django.utils import timezone
        from fleet.device_operations import execute_device_operation
        from organizations.models import Branch

        today = timezone.localdate()
        legal_owner = Organization.objects.create(name='Branch Transfer Legal Owner', code='BR-TRANSFER-OWNER')
        customer = Organization.objects.create(name='Branch Transfer Customer', code='BR-TRANSFER-CUSTOMER')
        source_branch = Branch.objects.create(organization=customer, name='Transfer Source Branch', code='BR-TRANSFER-SRC')
        target_branch = Branch.objects.create(organization=customer, name='Transfer Target Branch', code='BR-TRANSFER-TGT')
        subscription = Subscription.objects.create(
            contract_number='BRANCH-TRANSFER-ACCESS',
            customer_type='organization', organization=customer,
            start_date=today, end_date=today + timedelta(days=30), status='active',
        )
        device = Device.objects.create(
            imei='860000000000961', organization=legal_owner,
            current_holder_organization=customer, branch=source_branch,
            management_status='installed',
        )
        SubscriptionDevice.objects.create(
            subscription=subscription, device=device,
            start_date=subscription.start_date, end_date=subscription.end_date,
        )

        execute_device_operation(
            device=device, operation_type='transfer_branch', performed_by=None,
            target_branch=target_branch, subscription=subscription,
        )

        device.refresh_from_db()
        self.assertEqual(device.organization_id, legal_owner.id)
        self.assertEqual(device.current_holder_organization_id, customer.id)
        self.assertEqual(device.branch_id, target_branch.id)
        current_access = DeviceCustomerAccessPeriod.objects.get(device=device, ended_at__isnull=True)
        self.assertEqual(current_access.organization_id, customer.id)
        self.assertEqual(current_access.branch_id, target_branch.id)

    def test_vehicle_transfer_uses_contract_customer_not_legal_owner(self):
        from datetime import timedelta
        from django.utils import timezone
        from fleet.device_operations import execute_device_operation
        from fleet.models import Vehicle
        from organizations.models import Branch

        today = timezone.localdate()
        legal_owner = Organization.objects.create(name='Vehicle Transfer Legal Owner', code='VH-TRANSFER-OWNER')
        customer = Organization.objects.create(name='Vehicle Transfer Customer', code='VH-TRANSFER-CUSTOMER')
        branch = Branch.objects.create(organization=customer, name='Vehicle Transfer Branch', code='VH-TRANSFER-BRANCH')
        old_vehicle = Vehicle.objects.create(plate='77الف777', organization=customer, branch=branch)
        target_vehicle = Vehicle.objects.create(plate='88ب888', organization=customer, branch=branch)
        subscription = Subscription.objects.create(
            contract_number='VEHICLE-TRANSFER-ACCESS',
            customer_type='organization', organization=customer,
            start_date=today, end_date=today + timedelta(days=30), status='active',
        )
        device = Device.objects.create(
            imei='860000000000962', organization=legal_owner,
            current_holder_organization=customer, branch=branch, vehicle=old_vehicle,
            management_status='installed',
        )
        SubscriptionDevice.objects.create(
            subscription=subscription, device=device,
            start_date=subscription.start_date, end_date=subscription.end_date,
        )

        execute_device_operation(
            device=device, operation_type='transfer_vehicle', performed_by=None,
            target_vehicle=target_vehicle, subscription=subscription,
        )

        device.refresh_from_db()
        self.assertEqual(device.organization_id, legal_owner.id)
        self.assertEqual(device.current_holder_organization_id, customer.id)
        self.assertEqual(device.vehicle_id, target_vehicle.id)
        current_access = DeviceCustomerAccessPeriod.objects.get(device=device, ended_at__isnull=True)
        self.assertEqual(current_access.organization_id, customer.id)
        self.assertEqual(current_access.branch_id, branch.id)

    def test_contract_and_device_link_dates_cannot_be_reversed(self):
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
            device=Device.objects.create(imei='860000000000965'),
            start_date=today + timedelta(days=1),
            end_date=today,
        ))

    def test_access_and_ownership_period_dates_cannot_be_reversed(self):
        now = timezone.now()
        self.assert_database_rejects(lambda: DeviceCustomerAccessPeriod.objects.create(
            device=Device.objects.create(imei='860000000000966'),
            organization=self.organization,
            started_at=now,
            ended_at=now - timedelta(seconds=1),
        ))
        self.assert_database_rejects(lambda: DeviceOwnershipHistory.objects.create(
            device=Device.objects.create(imei='860000000000967'),
            organization=self.organization,
            started_at=now,
            ended_at=now - timedelta(seconds=1),
        ))

    def test_temporary_replacement_returns_to_warehouse_when_original_returns(self):
        from datetime import timedelta
        from django.utils import timezone
        from fleet.device_operations import execute_device_operation
        from fleet.models import DeviceBranchHistory, Vehicle
        from organizations.models import Branch

        today = timezone.localdate()
        legal_owner = Organization.objects.create(name='Loaner Legal Owner', code='LOANER-OWNER')
        customer = Organization.objects.create(name='Loaner Customer', code='LOANER-CUSTOMER')
        branch = Branch.objects.create(organization=customer, name='Loaner Branch', code='LOANER-BRANCH')
        vehicle = Vehicle.objects.create(plate='99ج999', organization=customer, branch=branch)
        subscription = Subscription.objects.create(
            contract_number='LOANER-RETURN-CONTRACT',
            customer_type='organization', organization=customer,
            start_date=today, end_date=today + timedelta(days=30), status='active',
        )
        source = Device.objects.create(
            imei='860000000000968', organization=legal_owner,
            current_holder_organization=customer, branch=branch, vehicle=vehicle,
            management_status='installed',
        )
        SubscriptionDevice.objects.create(
            subscription=subscription, device=source,
            start_date=subscription.start_date, end_date=subscription.end_date,
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=source, organization=customer, branch=branch, subscription=subscription,
        )
        source_branch_history = DeviceBranchHistory.objects.create(
            device=source,
            organization=customer,
            branch=branch,
            subscription=subscription,
        )
        loaner = Device.objects.create(
            imei='860000000000969', organization=legal_owner, management_status='warehouse',
        )

        execute_device_operation(
            device=source, operation_type='return_for_repair', performed_by=None,
            replacement_device=loaner, subscription=subscription,
            replacement_type='temporary_repair', replacement_method='warranty',
        )
        execute_device_operation(device=source, operation_type='repaired', performed_by=None)
        execute_device_operation(
            device=source, operation_type='disposition', performed_by=None,
            outcome_action='return_customer_no_vehicle',
        )

        loaner.refresh_from_db()
        source.refresh_from_db()
        from fleet.models import DeviceReplacementRelation
        relation = DeviceReplacementRelation.objects.get(source_device=source, replacement_device=loaner)
        source_branch_history.refresh_from_db()
        self.assertIsNotNone(source_branch_history.ended_at)
        self.assertIsNotNone(relation.returned_at)
        self.assertEqual(loaner.management_status, 'warehouse')
        # Returning a temporary loaner must not erase its separate legal owner.
        self.assertEqual(loaner.organization_id, legal_owner.id)
        self.assertIsNone(loaner.current_holder_organization_id)
        self.assertIsNone(loaner.active_subscription_link)
        self.assertFalse(DeviceCustomerAccessPeriod.objects.filter(
            device=loaner, ended_at__isnull=True,
        ).exists())
        self.assertTrue(DeviceCustomerAccessPeriod.objects.filter(
            device=source, organization=customer, ended_at__isnull=True,
        ).exists())

    def test_device_link_activity_follows_parent_contract_state(self):
        today = timezone.localdate()
        link = SubscriptionDevice.objects.create(
            subscription=self.subscription,
            device=self.device,
            start_date=self.subscription.start_date,
            end_date=self.subscription.end_date,
        )
        self.assertTrue(link.is_active)

        self.subscription.status = 'suspended'
        self.subscription.save(update_fields=['status', 'updated_at'])
        self.assertFalse(link.is_active)

        self.subscription.status = 'active'
        self.subscription.save(update_fields=['status', 'updated_at'])
        Subscription.objects.filter(pk=self.subscription.pk).update(end_date=today - timedelta(days=1))
        SubscriptionDevice.objects.filter(pk=link.pk).update(end_date=today - timedelta(days=1))
        link.refresh_from_db()
        self.assertFalse(link.is_active)

        Subscription.objects.filter(pk=self.subscription.pk).update(
            status='expired',
            end_date=today + timedelta(days=30),
        )
        SubscriptionDevice.objects.filter(pk=link.pk).update(
            end_date=today + timedelta(days=30),
        )
        link.refresh_from_db()
        self.assertFalse(link.is_active)

    def test_suspended_contract_cannot_open_live_access_or_accept_new_device(self):
        from rest_framework.exceptions import ValidationError
        from fleet.device_operations import _add_to_subscription, _open_customer_access

        link = SubscriptionDevice.objects.create(
            subscription=self.subscription,
            device=self.device,
            start_date=self.subscription.start_date,
            end_date=self.subscription.end_date,
        )
        self.subscription.status = 'suspended'
        self.subscription.save(update_fields=['status', 'updated_at'])

        self.assertIsNone(_open_customer_access(
            self.device,
            subscription=self.subscription,
            organization=self.organization,
            user=None,
        ))
        self.assertFalse(DeviceCustomerAccessPeriod.objects.filter(
            device=self.device,
            ended_at__isnull=True,
        ).exists())

        another_device = Device.objects.create(imei='860000000000970')
        with self.assertRaises(ValidationError):
            _add_to_subscription(another_device, self.subscription, operation=None)

    def test_device_cannot_be_assigned_to_a_different_holder_without_transfer(self):
        from rest_framework.exceptions import ValidationError
        from fleet.device_operations import _validate_device_customer_assignment

        self.device.current_holder_organization = self.other_organization
        self.device.save(update_fields=['current_holder_organization', 'updated_at'])

        with self.assertRaises(ValidationError):
            _validate_device_customer_assignment(self.device, self.subscription)

    def test_warehouse_device_cannot_have_live_customer_access_under_active_contract(self):
        from fleet.device_operations import _open_customer_access

        SubscriptionDevice.objects.create(
            subscription=self.subscription,
            device=self.device,
            start_date=self.subscription.start_date,
            end_date=self.subscription.end_date,
        )
        self.device.management_status = 'warehouse'
        self.device.save(update_fields=['management_status', 'updated_at'])

        self.assertFalse(self.device.is_data_active)
        self.assertIsNone(_open_customer_access(
            self.device,
            subscription=self.subscription,
            organization=self.organization,
            user=None,
        ))
        self.assertFalse(DeviceCustomerAccessPeriod.objects.filter(
            device=self.device,
            ended_at__isnull=True,
        ).exists())

    def test_disposal_closes_contract_access_and_legal_ownership_history(self):
        from fleet.device_operations import execute_device_operation

        legal_owner = self.organization
        customer = self.other_organization
        subscription = Subscription.objects.create(
            contract_number='DISPOSAL-ACCESS-CONTRACT',
            customer_type='organization',
            organization=customer,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=30),
            status='active',
        )
        device = Device.objects.create(
            imei='860000000000971',
            organization=legal_owner,
            current_holder_organization=customer,
            management_status='ready',
        )
        link = SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
        )
        DeviceOwnershipHistory.objects.create(device=device, organization=legal_owner)
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=customer,
            subscription=subscription,
        )

        execute_device_operation(
            device=device,
            operation_type='disposition',
            performed_by=None,
            outcome_action='dispose',
        )

        device.refresh_from_db()
        link.refresh_from_db()
        self.assertEqual(device.management_status, 'disposed')
        self.assertIsNone(device.organization_id)
        self.assertIsNone(device.owner_user_id)
        self.assertIsNotNone(link.unassigned_at)
        self.assertFalse(DeviceOwnershipHistory.objects.filter(
            device=device,
            ended_at__isnull=True,
        ).exists())
        self.assertFalse(DeviceCustomerAccessPeriod.objects.filter(
            device=device,
            ended_at__isnull=True,
        ).exists())

    def test_retire_and_direct_dispose_close_branch_and_ownership_lifecycle(self):
        from fleet.device_operations import execute_device_operation
        from fleet.models import DeviceBranchHistory
        from organizations.models import Branch

        branch = Branch.objects.create(
            organization=self.organization,
            name='Disposal Branch',
            code='DISPOSAL-BRANCH',
        )
        device = Device.objects.create(
            imei='860000000000972',
            organization=self.organization,
            current_holder_organization=self.organization,
            branch=branch,
            management_status='installed',
        )
        link = SubscriptionDevice.objects.create(
            subscription=self.subscription,
            device=device,
            start_date=self.subscription.start_date,
            end_date=self.subscription.end_date,
        )
        DeviceOwnershipHistory.objects.create(device=device, organization=self.organization)
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=self.organization,
            branch=branch,
            subscription=self.subscription,
        )
        DeviceBranchHistory.objects.create(
            device=device,
            organization=self.organization,
            branch=branch,
            subscription=self.subscription,
        )

        execute_device_operation(device=device, operation_type='retire', performed_by=None)
        device.refresh_from_db()
        self.assertEqual(device.management_status, 'unusable')
        self.assertFalse(DeviceBranchHistory.objects.filter(
            device=device,
            ended_at__isnull=True,
        ).exists())
        self.assertFalse(DeviceCustomerAccessPeriod.objects.filter(
            device=device,
            ended_at__isnull=True,
        ).exists())
        self.assertTrue(DeviceOwnershipHistory.objects.filter(
            device=device,
            ended_at__isnull=True,
        ).exists())

        execute_device_operation(device=device, operation_type='dispose', performed_by=None)
        device.refresh_from_db()
        link.refresh_from_db()
        self.assertEqual(device.management_status, 'disposed')
        self.assertIsNone(device.organization_id)
        self.assertIsNone(device.current_holder_organization_id)
        self.assertIsNotNone(link.unassigned_at)
        self.assertFalse(DeviceOwnershipHistory.objects.filter(
            device=device,
            ended_at__isnull=True,
        ).exists())

    def test_unserviceable_device_cannot_be_assigned_to_a_new_contract(self):
        from rest_framework.exceptions import ValidationError
        from fleet.device_operations import _validate_device_customer_assignment

        self.device.management_status = 'in_repair'
        self.device.save(update_fields=['management_status', 'updated_at'])

        with self.assertRaises(ValidationError):
            _validate_device_customer_assignment(self.device, self.subscription)

    def test_customer_holder_without_a_contract_cannot_open_live_access(self):
        from fleet.device_operations import _open_customer_access

        self.device.current_holder_organization = self.organization
        self.device.save(update_fields=['current_holder_organization', 'updated_at'])

        self.assertIsNone(_open_customer_access(
            self.device,
            organization=self.organization,
            user=None,
        ))
        self.assertFalse(DeviceCustomerAccessPeriod.objects.filter(
            device=self.device,
            ended_at__isnull=True,
        ).exists())

    def test_lost_device_closes_old_branch_history_for_temporary_replacement(self):
        from fleet.device_operations import execute_device_operation
        from fleet.models import DeviceBranchHistory
        from organizations.models import Branch

        branch = Branch.objects.create(
            organization=self.organization,
            name='Lost Device Branch',
            code='LOST-DEVICE-BRANCH',
        )
        source = Device.objects.create(
            imei='860000000000973',
            organization=self.other_organization,
            current_holder_organization=self.organization,
            branch=branch,
            management_status='installed',
        )
        SubscriptionDevice.objects.create(
            subscription=self.subscription,
            device=source,
            start_date=self.subscription.start_date,
            end_date=self.subscription.end_date,
        )
        source_history = DeviceBranchHistory.objects.create(
            device=source,
            organization=self.organization,
            branch=branch,
            subscription=self.subscription,
        )
        replacement = Device.objects.create(
            imei='860000000000974',
            management_status='warehouse',
        )

        execute_device_operation(
            device=source,
            operation_type='lost',
            performed_by=None,
            replacement_device=replacement,
            subscription=self.subscription,
            replacement_type='temporary_repair',
            replacement_method='warranty',
        )

        source_history.refresh_from_db()
        self.assertIsNotNone(source_history.ended_at)
        self.assertTrue(DeviceBranchHistory.objects.filter(
            device=replacement,
            organization=self.organization,
            branch=branch,
            subscription=self.subscription,
            ended_at__isnull=True,
        ).exists())

        execute_device_operation(
            device=source,
            operation_type='found',
            performed_by=None,
            subscription=self.subscription,
        )
        self.assertFalse(DeviceBranchHistory.objects.filter(
            device=source,
            ended_at__isnull=True,
        ).exists())

    def test_device_api_cannot_change_legal_owner_without_lifecycle_transfer(self):
        from fleet.serializers import DeviceSerializer

        device = Device.objects.create(
            imei='860000000000975',
            organization=self.organization,
        )
        serializer = DeviceSerializer(
            instance=device,
            data={'organization': self.other_organization.id},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('organization', serializer.errors)

    def test_device_creation_records_initial_legal_ownership_history(self):
        from fleet.serializers import DeviceSerializer

        serializer = DeviceSerializer(data={
            'imei': '860000000000976',
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

    def test_future_contract_creates_scheduled_access_without_early_live_visibility(self):
        from datetime import datetime, time, timedelta
        from fleet.device_operations import _close_customer_access, _open_customer_access

        today = timezone.localdate()
        future_start = today + timedelta(days=5)
        future_end = future_start + timedelta(days=30)
        Subscription.objects.filter(pk=self.subscription.pk).update(
            start_date=future_start,
            end_date=future_end,
        )
        self.subscription.refresh_from_db()
        device = Device.objects.create(
            imei='860000000000978',
            current_holder_organization=self.organization,
            management_status='installed',
        )
        SubscriptionDevice.objects.create(
            subscription=self.subscription,
            device=device,
            start_date=future_start,
            end_date=future_end,
        )

        period = _open_customer_access(
            device,
            subscription=self.subscription,
            organization=self.organization,
            user=None,
        )
        expected_start = timezone.make_aware(
            datetime.combine(future_start, time.min),
            timezone.get_current_timezone(),
        )
        self.assertIsNotNone(period)
        self.assertEqual(period.started_at, expected_start)
        self.assertFalse(device.is_data_active)

        _close_customer_access(
            device,
            when=timezone.now(),
            subscription=self.subscription,
        )
        period.refresh_from_db()
        self.assertEqual(period.ended_at, period.started_at)

