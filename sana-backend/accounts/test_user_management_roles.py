from datetime import timedelta

from django.test import TestCase, RequestFactory
from django.contrib import admin as django_admin
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User, UserSession
from accounts.admin import UserAdmin
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

    def test_branch_manager_cannot_read_full_organization_details(self):
        self.client.force_authenticate(self.branch_manager)

        own_profile = self.client.get('/api/users/me/')
        self.assertEqual(own_profile.status_code, 200)
        self.assertIsNone(own_profile.data['organization_data'])

        own_user_list = self.client.get('/api/users/')
        self.assertEqual(own_user_list.status_code, 200)
        payload = own_user_list.data['results'] if isinstance(own_user_list.data, dict) else own_user_list.data
        self.assertEqual(len(payload), 1)
        self.assertIsNone(payload[0]['organization_data'])

        self.client.force_authenticate(self.admin)
        admin_list = self.client.get('/api/users/')
        self.assertEqual(admin_list.status_code, 200)
        admin_payload = admin_list.data['results'] if isinstance(admin_list.data, dict) else admin_list.data
        branch_user = next(item for item in admin_payload if item['id'] == self.branch_manager.id)
        self.assertEqual(branch_user['organization_data']['code'], self.organization.code)

    def test_branch_manager_responses_do_not_expose_parent_organization(self):
        from accounts.serializers import CustomTokenObtainPairSerializer
        from fleet.models import Driver

        self.client.force_authenticate(self.branch_manager)

        profile = self.client.get('/api/users/me/')
        self.assertEqual(profile.status_code, 200)
        self.assertIsNone(profile.data['organization'])
        self.assertIsNone(profile.data['organization_name'])
        self.assertIsNone(profile.data['organization_data'])

        branch_list = self.client.get('/api/branches/')
        self.assertEqual(branch_list.status_code, 200)
        branch_payload = branch_list.data['results'] if isinstance(branch_list.data, dict) else branch_list.data
        own_branch = next(item for item in branch_payload if item['id'] == self.branch.id)
        self.assertIsNone(own_branch['organization'])
        self.assertIsNone(own_branch['organization_name'])

        branch_detail = self.client.get(f'/api/branches/{self.branch.id}/')
        self.assertEqual(branch_detail.status_code, 200)
        self.assertIsNone(branch_detail.data['organization'])
        self.assertIsNone(branch_detail.data['organization_name'])

        Driver.objects.create(
            first_name='Branch',
            last_name='Driver',
            mobile='09120000000',
            organization=self.organization,
            branch=self.branch,
        )
        drivers = self.client.get('/api/drivers/')
        self.assertEqual(drivers.status_code, 200)
        driver_payload = drivers.data['results'] if isinstance(drivers.data, dict) else drivers.data
        self.assertEqual(len(driver_payload), 1)
        self.assertIsNone(driver_payload[0]['organization'])
        self.assertIsNone(driver_payload[0]['organization_name'])

        token = CustomTokenObtainPairSerializer.get_token(self.branch_manager)
        self.assertNotIn('organization_id', token.payload)
        self.assertNotIn('organization_name', token.payload)
        self.assertEqual(token.payload['branch_id'], self.branch.id)

    def test_branch_manager_user_list_contains_only_self(self):
        User.objects.create_user(
            username='another-branch-user', password='test-password-123',
            role='branch_manager', account_type='organization',
            organization=self.organization, branch=self.branch,
        )
        self.client.force_authenticate(self.branch_manager)
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, 200)
        payload = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertEqual([item['id'] for item in payload], [self.branch_manager.id])

    def test_company_manager_can_manage_legacy_branch_user_without_organization_fk(self):
        legacy_user = User.objects.create_user(
            username='legacy-branch-user', password='test-password-123',
            role='branch_manager', account_type='organization', branch=self.branch,
        )
        self.client.force_authenticate(self.company_manager)
        listed = self.client.get('/api/users/')
        payload = listed.data['results'] if isinstance(listed.data, dict) else listed.data
        self.assertIn(legacy_user.id, [item['id'] for item in payload])
        legacy_payload = next(item for item in payload if item['id'] == legacy_user.id)
        self.assertEqual(legacy_payload['organization_name'], self.organization.name)
        archived = self.client.post(f'/api/users/{legacy_user.id}/archive/', {}, format='json')
        self.assertEqual(archived.status_code, 200)

    def test_company_manager_does_not_list_branch_manager_with_mismatched_tenant_links(self):
        inconsistent = User.objects.create_user(
            username='tenant-mismatch-branch-manager', password='test-password-123',
            role='branch_manager', account_type='organization',
            organization=self.organization, branch=self.other_branch,
        )
        self.client.force_authenticate(self.company_manager)
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, 200)
        payload = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertNotIn(inconsistent.id, [item['id'] for item in payload])

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

    def test_branch_manager_cannot_create_vehicles_or_devices(self):
        self.client.force_authenticate(self.branch_manager)
        vehicle_response = self.client.post('/api/vehicles/', {
            'plate': '12الف345',
            'branch': self.branch.id,
        }, format='json')
        device_response = self.client.post('/api/devices/', {
            'imei': '123456789012345',
            'branch': self.branch.id,
        }, format='json')
        self.assertEqual(vehicle_response.status_code, 403)
        self.assertEqual(device_response.status_code, 403)

    def test_company_manager_can_deactivate_user_and_sessions_are_revoked(self):
        target = User.objects.create_user(
            username='deactivate-target', password='test-password-123',
            role='branch_manager', account_type='organization',
            organization=self.organization, branch=self.branch,
        )
        session = UserSession.objects.create(
            user=target, expires_at=timezone.now() + timedelta(hours=2),
        )
        self.client.force_authenticate(self.company_manager)
        response = self.client.patch(
            f'/api/users/{target.id}/',
            {'is_active': False},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        target.refresh_from_db()
        session.refresh_from_db()
        self.assertFalse(target.is_active)
        self.assertIsNotNone(session.revoked_at)

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

        restore_response = self.client.post(f'/api/users/{target.id}/restore/', {}, format='json')
        self.assertEqual(restore_response.status_code, 200)
        target.refresh_from_db()
        self.assertIsNone(target.archived_at)
        self.assertTrue(target.is_active)

    def test_company_manager_cannot_archive_users_outside_own_organization(self):
        foreign = User.objects.create_user(
            username='foreign-user', password='test-password-123',
            role='branch_manager', account_type='organization',
            organization=self.other_organization, branch=self.other_branch,
        )
        self.client.force_authenticate(self.company_manager)
        response = self.client.post(f'/api/users/{foreign.id}/archive/', {}, format='json')
        self.assertEqual(response.status_code, 404)


    def test_api_created_site_admin_gets_django_admin_permissions(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post('/api/users/', {
            'username': 'new-site-admin',
            'password': 'test-password-123',
            'account_type': 'admin',
            'role': 'site_admin',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        created = User.objects.get(username='new-site-admin')
        self.assertTrue(created.is_staff)
        self.assertTrue(created.is_superuser)

    def test_demoting_site_admin_revokes_django_admin_permissions(self):
        second_admin = User.objects.create_user(
            username='second-site-admin', password='test-password-123',
            role='site_admin', account_type='admin', is_staff=True, is_superuser=True,
        )
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f'/api/users/{second_admin.id}/',
            {'role': 'personal_user', 'account_type': 'personal'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        second_admin.refresh_from_db()
        self.assertEqual(second_admin.role, 'personal_user')
        self.assertFalse(second_admin.is_staff)
        self.assertFalse(second_admin.is_superuser)

    def test_site_admin_cannot_demote_or_deactivate_own_account(self):
        self.client.force_authenticate(self.admin)
        demote = self.client.patch(
            f'/api/users/{self.admin.id}/',
            {'role': 'personal_user', 'account_type': 'personal'},
            format='json',
        )
        deactivate = self.client.patch(
            f'/api/users/{self.admin.id}/',
            {'is_active': False},
            format='json',
        )
        self.assertEqual(demote.status_code, 400)
        self.assertEqual(deactivate.status_code, 400)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, 'site_admin')
        self.assertTrue(self.admin.is_active)
        self.assertTrue(self.admin.is_staff)
        self.assertTrue(self.admin.is_superuser)


    def test_archiving_site_admin_revokes_sessions_without_removing_last_admin(self):
        second_admin = User.objects.create_user(
            username='archived-site-admin', password='test-password-123',
            role='site_admin', account_type='admin', is_staff=True, is_superuser=True,
        )
        session = UserSession.objects.create(
            user=second_admin, expires_at=timezone.now() + timedelta(hours=2),
        )
        self.client.force_authenticate(self.admin)
        response = self.client.post(f'/api/users/{second_admin.id}/archive/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        second_admin.refresh_from_db()
        session.refresh_from_db()
        self.assertIsNotNone(second_admin.archived_at)
        self.assertFalse(second_admin.is_active)
        self.assertIsNotNone(session.revoked_at)
        self.assertTrue(User.objects.filter(role='site_admin', is_active=True).exists())

    def test_restoring_site_admin_restores_django_admin_permissions(self):
        target = User.objects.create_user(
            username='restore-site-admin', password='test-password-123',
            role='site_admin', account_type='admin',
        )
        # Simulate a legacy row whose Django admin flags drifted from its role.
        target.is_staff = False
        target.is_superuser = False
        target.save(update_fields=['is_staff', 'is_superuser'])
        self.client.force_authenticate(self.admin)
        archived = self.client.post(f'/api/users/{target.id}/archive/', {}, format='json')
        self.assertEqual(archived.status_code, 200)
        restored = self.client.post(f'/api/users/{target.id}/restore/', {}, format='json')
        self.assertEqual(restored.status_code, 200)
        target.refresh_from_db()
        self.assertTrue(target.is_staff)
        self.assertTrue(target.is_superuser)


    def test_django_admin_save_model_synchronizes_role_permissions(self):
        request = RequestFactory().post('/admin/accounts/user/')
        request.user = self.admin
        model_admin = UserAdmin(User, django_admin.site)
        target = User.objects.create_user(
            username='admin-ui-target', password='test-password-123',
            role='site_admin', account_type='admin', is_staff=True, is_superuser=True,
        )
        target.role = 'personal_user'
        target.account_type = 'personal'
        model_admin.save_model(request, target, form=None, change=True)
        target.refresh_from_db()
        self.assertFalse(target.is_staff)
        self.assertFalse(target.is_superuser)

    def test_django_admin_cannot_demote_or_deactivate_own_account(self):
        request = RequestFactory().post('/admin/accounts/user/')
        request.user = self.admin
        model_admin = UserAdmin(User, django_admin.site)
        self.admin.role = 'personal_user'
        self.admin.account_type = 'personal'
        with self.assertRaises(DjangoValidationError):
            model_admin.save_model(request, self.admin, form=None, change=True)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, 'site_admin')
        self.assertTrue(self.admin.is_active)


    def test_user_manager_keeps_site_admin_role_and_permissions_consistent(self):
        admin_user = User.objects.create_user(
            username='manager-created-admin', password='test-password-123',
            role='site_admin', account_type='admin',
        )
        ordinary_user = User.objects.create_user(
            username='manager-created-ordinary', password='test-password-123',
            role='personal_user', account_type='personal', is_staff=True, is_superuser=True,
        )
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertFalse(ordinary_user.is_staff)
        self.assertFalse(ordinary_user.is_superuser)

    def test_create_superuser_rejects_non_admin_application_role(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                username='invalid-superuser-role', password='test-password-123',
                role='main_user', account_type='organization',
            )


    def test_site_admin_role_change_revokes_all_existing_sessions(self):
        target = User.objects.create_user(
            username='role-change-session-target', password='test-password-123',
            role='site_admin', account_type='admin',
        )
        session = UserSession.objects.create(
            user=target, expires_at=timezone.now() + timedelta(hours=2),
        )
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f'/api/users/{target.id}/',
            {'role': 'personal_user', 'account_type': 'personal'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertIsNotNone(session.revoked_at)

    def test_company_manager_branch_transfer_revokes_user_sessions(self):
        other_branch = Branch.objects.create(
            organization=self.organization, name='Second Branch', code='ROLE-BRANCH-3'
        )
        target = User.objects.create_user(
            username='branch-transfer-session-target', password='test-password-123',
            role='branch_manager', account_type='organization',
            organization=self.organization, branch=self.branch,
        )
        session = UserSession.objects.create(
            user=target, expires_at=timezone.now() + timedelta(hours=2),
        )
        self.client.force_authenticate(self.company_manager)
        response = self.client.patch(
            f'/api/users/{target.id}/',
            {'branch': other_branch.id},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertIsNotNone(session.revoked_at)
