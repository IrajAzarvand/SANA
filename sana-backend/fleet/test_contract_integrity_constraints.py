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
        self.assert_database_rejects(lambda: SubscriptionDevice.objects.create(
            subscription=self.other_subscription,
            device=self.device,
            start_date=self.other_subscription.start_date,
            end_date=self.other_subscription.end_date,
        ))

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
        from fleet.device_operations import execute_device_operation
        from fleet.models import Branch
        from django.utils import timezone

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
