from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User, UserSession
from organizations.models import Organization, Branch


class UserManagementRoleBoundaryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = Organization.objects.create(name='Role Test Org', code='ROLE-ORG')
        self.other_organization = Organization.objects.create(name='Other Role Org', code='ROLE-ORG-2')
        self.branch = Branch.objects.create(
            organization=self.organization, name='Role Test Branch', code='ROLE-BRANCH'
        )
        self.other_branch = Branch.objects.create(
            organization=self.other_organization, name='Other Branch', code='ROLE-BRANCH-2'
        )
        self.admin = User.objects.create_user(
            username='role-admin', password='test-password-123',
            role='site_admin', account_type='admin', is_staff=True, is_superuser=True,
        )
        self.company_manager = User.objects.create_user(
            username='role-company-manager', password='test-password-123',
            role='main_user', account_type='organization', organization=self.organization,
        )
        self.branch_manager = User.objects.create_user(
            username='role-branch-manager', password='test-password-123',
            role='branch_manager', account_type='organization',
            organization=self.organization, branch=self.branch,
        )

    def test_branch_manager_user_list_contains_only_self(self):
        User.objects.create_user(
            username='another-branch-user', password='test-password-123',
            role='branch_manager', account_type='organization',
            organization=self.organization, branch=self.branch,
        )
        self.client.force_authenticate(self.branch_manager)
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, 200)
        payload = response.data.get('results', response.data)
        self.assertEqual([item['id'] for item in payload], [self.branch_manager.id])

    def test_branch_manager_cannot_create_or_archive_users(self):
        self.client.force_authenticate(self.branch_manager)
        create_response = self.client.post('/api/users/', {
            'username': 'forbidden-new-user',
            'password': 'test-password-123',
            'account_type': 'organization',
            'role': 'branch_manager',
            'organization': self.organization.id,
            'branch': self.branch.id,
        }, format='json')
        self.assertEqual(create_response.status_code, 403)

        target = User.objects.create_user(
            username='archive-target', password='test-password-123',
            role='branch_manager', account_type='organization',
            organization=self.organization, branch=self.branch,
        )
        archive_response = self.client.post(f'/api/users/{target.id}/archive/', {}, format='json')
        self.assertEqual(archive_response.status_code, 403)

    def test_branch_manager_cannot_manage_branches_or_drivers(self):
        self.client.force_authenticate(self.branch_manager)
        branch_response = self.client.post('/api/branches/', {
            'name': 'Forbidden Branch', 'code': 'FORBIDDEN', 'organization': self.organization.id,
        }, format='json')
        driver_response = self.client.post('/api/drivers/', {
            'first_name': 'Test', 'last_name': 'Driver', 'organization': self.organization.id,
            'branch': self.branch.id,
        }, format='json')
        self.assertEqual(branch_response.status_code, 403)
        self.assertEqual(driver_response.status_code, 403)

    def test_company_manager_can_create_branch_manager_only_in_own_organization(self):
        self.client.force_authenticate(self.company_manager)
        allowed = self.client.post('/api/users/', {
            'username': 'new-branch-manager',
            'password': 'test-password-123',
            'account_type': 'organization',
            'role': 'branch_manager',
            'branch': self.branch.id,
        }, format='json')
        self.assertEqual(allowed.status_code, 201)
        self.assertEqual(allowed.data['organization'], self.organization.id)

        denied = self.client.post('/api/users/', {
            'username': 'foreign-branch-manager',
            'password': 'test-password-123',
            'account_type': 'organization',
            'role': 'branch_manager',
            'branch': self.other_branch.id,
        }, format='json')
        self.assertEqual(denied.status_code, 400)

    def test_destroy_archives_user_and_revokes_sessions_instead_of_deleting(self):
        self.client.force_authenticate(self.company_manager)
        target = User.objects.create_user(
            username='archive-me', password='test-password-123',
            role='branch_manager', account_type='organization',
            organization=self.organization, branch=self.branch,
        )
        session = UserSession.objects.create(
            user=target, expires_at=timezone.now() + timedelta(hours=2),
        )
        response = self.client.delete(f'/api/users/{target.id}/')
        self.assertEqual(response.status_code, 204)
        target.refresh_from_db()
        session.refresh_from_db()
        self.assertIsNotNone(target.archived_at)
        self.assertFalse(target.is_active)
        self.assertIsNotNone(session.revoked_at)
        self.assertTrue(User.objects.filter(pk=target.pk).exists())

    def test_company_manager_cannot_archive_users_outside_own_organization(self):
        foreign = User.objects.create_user(
            username='foreign-user', password='test-password-123',
            role='branch_manager', account_type='organization',
            organization=self.other_organization, branch=self.other_branch,
        )
        self.client.force_authenticate(self.company_manager)
        response = self.client.post(f'/api/users/{foreign.id}/archive/', {}, format='json')
        self.assertEqual(response.status_code, 404)
