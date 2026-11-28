from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from fleet.customer_access import active_customer_access_periods
from fleet.models import Device, DeviceCustomerAccessPeriod
from organizations.models import Branch, Organization, Subscription, SubscriptionDevice


class BranchManagerAccessWindowTests(TestCase):
    """Branch access must be bounded by every contract and assignment window."""

    def setUp(self):
        self.now = timezone.now()
        today = timezone.localdate(self.now)
        self.organization = Organization.objects.create(
            name='Branch Access Window Organization',
            code='BRANCH-ACCESS-WINDOW-ORG',
        )
        self.branch = Branch.objects.create(
            organization=self.organization,
            name='Branch Access Window Branch',
            code='BRANCH-ACCESS-WINDOW',
        )
        self.manager = User.objects.create_user(
            username='branch_access_window_manager',
            password='test-password',
            role='branch_manager',
            account_type='organization',
            organization=self.organization,
            branch=self.branch,
        )
        self.device = Device.objects.create(
            imei='860000000009981',
            organization=self.organization,
            branch=self.branch,
            management_status='installed',
        )
        self.subscription = Subscription.objects.create(
            contract_number='BRANCH-ACCESS-WINDOW-CONTRACT',
            customer_type='organization',
            organization=self.organization,
            start_date=today - timedelta(days=2),
            end_date=today + timedelta(days=10),
            status='active',
        )
        self.link = SubscriptionDevice.objects.create(
            subscription=self.subscription,
            device=self.device,
            start_date=self.subscription.start_date,
            end_date=self.subscription.end_date,
        )
        SubscriptionDevice.objects.filter(pk=self.link.pk).update(
            assigned_at=self.now - timedelta(hours=1)
        )
        self.period = DeviceCustomerAccessPeriod.objects.create(
            device=self.device,
            organization=self.organization,
            subscription=self.subscription,
            branch=self.branch,
            started_at=self.now - timedelta(minutes=30),
        )

    def has_branch_access(self, *, now=None):
        return active_customer_access_periods(
            organization_id=self.organization.pk,
            branch_id=self.branch.pk,
            now=now or self.now,
        ).filter(device=self.device).exists()

    def test_branch_manager_has_access_inside_all_valid_windows(self):
        self.assertTrue(self.has_branch_access())

    def test_access_period_start_is_enforced(self):
        self.assertFalse(
            self.has_branch_access(now=self.period.started_at - timedelta(seconds=1))
        )

    def test_access_period_end_revokes_access_immediately(self):
        self.period.ended_at = self.now - timedelta(seconds=1)
        self.period.save(update_fields=['ended_at'])

        self.assertFalse(self.has_branch_access())

    def test_contract_start_date_is_enforced(self):
        self.subscription.start_date = timezone.localdate(self.now) + timedelta(days=1)
        self.subscription.save(update_fields=['start_date'])

        self.assertFalse(self.has_branch_access())

    def test_contract_end_date_revokes_access_even_if_access_period_is_open(self):
        self.subscription.end_date = timezone.localdate(self.now) - timedelta(days=1)
        self.subscription.save(update_fields=['end_date'])

        self.assertFalse(self.has_branch_access())

    def test_device_assignment_start_date_is_enforced(self):
        self.link.start_date = timezone.localdate(self.now) + timedelta(days=1)
        self.link.save(update_fields=['start_date'])

        self.assertFalse(self.has_branch_access())

    def test_device_assignment_end_date_revokes_access(self):
        self.link.end_date = timezone.localdate(self.now) - timedelta(days=1)
        self.link.save(update_fields=['end_date'])

        self.assertFalse(self.has_branch_access())

    def test_future_assignment_timestamp_does_not_grant_access_early(self):
        SubscriptionDevice.objects.filter(pk=self.link.pk).update(
            assigned_at=self.now + timedelta(minutes=1)
        )

        self.assertFalse(self.has_branch_access())

    def test_unassigned_device_link_does_not_grant_access(self):
        SubscriptionDevice.objects.filter(pk=self.link.pk).update(
            unassigned_at=self.now - timedelta(seconds=1)
        )

        self.assertFalse(self.has_branch_access())

    def test_inactive_branch_does_not_grant_access(self):
        self.branch.status = 'inactive'
        self.branch.save(update_fields=['status'])

        self.assertFalse(self.has_branch_access())

    def test_suspended_contract_does_not_grant_access(self):
        self.subscription.status = 'suspended'
        self.subscription.save(update_fields=['status'])

        self.assertFalse(self.has_branch_access())
