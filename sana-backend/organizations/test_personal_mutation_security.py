from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from organizations.models import (
    Branch,
    Organization,
    Subscription,
    SubscriptionPayment,
)


class PersonalMutationSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.today = timezone.localdate()
        self.personal_user = User.objects.create_user(
            username='personal-mutation-owner',
            password='test-password',
            account_type='personal',
            role='personal_user',
        )
        self.organization_a = Organization.objects.create(
            name='سازمان اول',
            code='SEC-ORG-A',
        )
        self.organization_b = Organization.objects.create(
            name='سازمان دوم',
            code='SEC-ORG-B',
        )
        self.main_user = User.objects.create_user(
            username='mutation-main-user',
            password='test-password',
            account_type='organization',
            role='main_user',
            organization=self.organization_a,
        )
        self.branch_manager = User.objects.create_user(
            username='mutation-branch-manager',
            password='test-password',
            account_type='organization',
            role='branch_manager',
            organization=self.organization_a,
        )
        self.branch = Branch.objects.create(
            organization=self.organization_a,
            name='شعبه اول',
            code='SEC-BR-A',
        )
        self.subscription = Subscription.objects.create(
            contract_number='SEC-PERSONAL-001',
            customer_type='personal',
            user=self.personal_user,
            start_date=self.today - timedelta(days=5),
            end_date=self.today + timedelta(days=30),
            status='active',
            price=100000,
        )
        self.payment = SubscriptionPayment.objects.create(
            subscription=self.subscription,
            amount=10000,
            received_at=self.today,
        )

    def test_personal_customer_cannot_create_a_branch(self):
        self.client.force_authenticate(user=self.personal_user)

        response = self.client.post(
            '/api/branches/',
            {
                'organization': self.organization_b.id,
                'name': 'شعبه غیرمجاز',
                'code': 'SEC-UNAUTH-BR',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Branch.objects.filter(code='SEC-UNAUTH-BR').exists())

    def test_main_user_cannot_create_a_branch_in_another_organization(self):
        self.client.force_authenticate(user=self.main_user)

        response = self.client.post(
            '/api/branches/',
            {
                'organization': self.organization_b.id,
                'name': 'شعبه سازمان دیگر',
                'code': 'SEC-CROSS-ORG',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201, response.data)
        created = Branch.objects.get(code='SEC-CROSS-ORG')
        self.assertEqual(created.organization_id, self.organization_a.id)

    def test_main_user_cannot_move_an_existing_branch_to_another_organization(self):
        self.client.force_authenticate(user=self.main_user)

        response = self.client.patch(
            f'/api/branches/{self.branch.id}/',
            {'organization': self.organization_b.id, 'name': 'نام جدید'},
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.branch.refresh_from_db()
        self.assertEqual(self.branch.organization_id, self.organization_a.id)
        self.assertEqual(self.branch.name, 'نام جدید')

    def test_branch_manager_cannot_mutate_branches(self):
        self.client.force_authenticate(user=self.branch_manager)

        response = self.client.post(
            '/api/branches/',
            {
                'organization': self.organization_a.id,
                'name': 'شعبه مدیر',
                'code': 'SEC-BR-MANAGER',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Branch.objects.filter(code='SEC-BR-MANAGER').exists())

    def test_personal_customer_cannot_reallocate_own_payment(self):
        self.client.force_authenticate(user=self.personal_user)

        response = self.client.post(
            f'/api/subscription-payments/{self.payment.id}/allocate/',
            {'allocation_mode': 'automatic'},
            format='json',
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.payment.allocations.exists())
