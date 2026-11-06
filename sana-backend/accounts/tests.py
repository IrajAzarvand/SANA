from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from organizations.models import Branch, Organization, Subscription


class ContractExpirationAccessTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.organization = Organization.objects.create(
            name='Test Organization',
            code='TEST-ORG-001',
        )
        self.organization_user = User.objects.create_user(
            username='org-manager',
            password='test-password-123',
            account_type='organization',
            role='main_user',
            organization=self.organization,
        )
        self.subscription = Subscription.objects.create(
            contract_number='TEST-CONTRACT-001',
            customer_type='organization',
            organization=self.organization,
            start_date=self.today - timedelta(days=30),
            end_date=self.today - timedelta(days=1),
            status='active',
        )
        self.client = APIClient()

    def authenticate_as(self, user):
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        return str(refresh)

    def test_expired_organization_contract_blocks_existing_access_token(self):
        self.authenticate_as(self.organization_user)
        response = self.client.get('/api/users/me/')
        self.assertEqual(response.status_code, 401)

    def test_expired_organization_contract_blocks_refresh_token(self):
        refresh = self.authenticate_as(self.organization_user)
        response = self.client.post('/api/auth/refresh/', {'refresh': refresh}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('detail', response.data)

    def test_contract_is_valid_through_its_end_date(self):
        self.subscription.end_date = self.today
        self.subscription.save(update_fields=['end_date'])
        self.authenticate_as(self.organization_user)
        response = self.client.get('/api/users/me/')
        self.assertEqual(response.status_code, 200)

    def test_expired_personal_contract_blocks_existing_access_token(self):
        personal_user = User.objects.create_user(
            username='personal-customer',
            password='test-password-123',
            account_type='personal',
            role='personal_user',
        )
        Subscription.objects.create(
            contract_number='TEST-CONTRACT-PERSONAL',
            customer_type='personal',
            user=personal_user,
            start_date=self.today - timedelta(days=30),
            end_date=self.today - timedelta(days=1),
            status='active',
        )
        self.authenticate_as(personal_user)
        response = self.client.get('/api/users/me/')
        self.assertEqual(response.status_code, 401)

    def test_branch_user_uses_parent_organization_contract(self):
        branch = Branch.objects.create(
            organization=self.organization,
            name='Test Branch',
            code='TEST-BRANCH-001',
        )
        branch_user = User.objects.create_user(
            username='branch-manager',
            password='test-password-123',
            account_type='organization',
            role='branch_manager',
            branch=branch,
            # Intentionally omit organization to verify fallback through branch.
        )
        self.subscription.end_date = self.today
        self.subscription.save(update_fields=['end_date'])
        self.authenticate_as(branch_user)
        allowed_response = self.client.get('/api/users/me/')
        self.assertEqual(allowed_response.status_code, 200)

        self.subscription.end_date = self.today - timedelta(days=1)
        self.subscription.save(update_fields=['end_date'])
        denied_response = self.client.get('/api/users/me/')
        self.assertEqual(denied_response.status_code, 401)

    def test_site_admin_is_not_blocked_by_customer_contracts(self):
        admin = User.objects.create_user(
            username='site-admin',
            password='test-password-123',
            account_type='admin',
            role='site_admin',
            is_staff=True,
            is_superuser=True,
        )
        self.authenticate_as(admin)
        response = self.client.get('/api/users/me/')
        self.assertEqual(response.status_code, 200)


class UsernameAvailabilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='availability-admin',
            password='test-password-123',
            account_type='admin',
            role='site_admin',
            is_staff=True,
            is_superuser=True,
        )
        self.organization_user = User.objects.create_user(
            username='existing-org-user',
            password='test-password-123',
            account_type='organization',
            role='main_user',
        )

    def authenticate_as(self, user):
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def test_site_admin_sees_username_used_by_another_account_type_as_taken(self):
        self.authenticate_as(self.admin)

        response = self.client.get(
            '/api/users/username-availability/',
            {'username': self.organization_user.username},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'available': False, 'exists': True})

    def test_site_admin_sees_unused_username_as_available(self):
        self.authenticate_as(self.admin)

        response = self.client.get(
            '/api/users/username-availability/',
            {'username': 'new-personal-user'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'available': True, 'exists': False})

    def test_username_availability_requires_site_admin(self):
        regular_user = User.objects.create_user(
            username='availability-regular-user',
            password='test-password-123',
            account_type='personal',
            role='personal_user',
        )
        self.authenticate_as(regular_user)

        response = self.client.get(
            '/api/users/username-availability/',
            {'username': 'existing-org-user'},
        )

        self.assertEqual(response.status_code, 403)

    def test_username_availability_rejects_blank_username(self):
        self.authenticate_as(self.admin)

        response = self.client.get('/api/users/username-availability/')

        self.assertEqual(response.status_code, 400)
