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

    def test_device_cannot_have_both_legal_owner_types(self):
        from accounts.models import User

        user = User.objects.create_user(username='integrity_owner_user', password='test-password')
        self.assert_database_rejects(lambda: Device.objects.create(
            imei='860000000000956',
            organization=self.organization,
            owner_user=user,
        ))

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
        self.assertGreaterEqual(DeviceCustomerAccessPeriod.objects.filter(
            device=device, ended_at__isnull=False,
        ).count(), 2)

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
        from fleet.models import Vehicle
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

