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
