from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from organizations.models import Organization, Subscription


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
