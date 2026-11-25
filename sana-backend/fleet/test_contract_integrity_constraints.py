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
        serializer = DeviceSerializer(data={
            'imei': '860000000000971',
            'organization': self.organization.id,
            'current_holder_organization': self.organization.id,
            'branch': branch.id,
            'vehicle': vehicle.id,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('current_holder_organization', serializer.errors)
        self.assertIn('branch', serializer.errors)
        self.assertIn('vehicle', serializer.errors)

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
