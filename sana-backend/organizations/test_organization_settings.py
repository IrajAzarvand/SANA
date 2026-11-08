from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from organizations.models import Organization


class OrganizationSettingsAPITests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name='شرکت اول',
            code='ORG-SETTINGS-01',
            registration_number='1001',
            economy_code='2001',
            phone='02111111111',
        )
        self.other_organization = Organization.objects.create(
            name='شرکت دوم',
            code='ORG-SETTINGS-02',
        )
        self.admin = User.objects.create_user(
            username='settings-admin',
            password='Password-123456',
            account_type='admin',
            role='site_admin',
        )
        self.manager = User.objects.create_user(
            username='settings-manager',
            password='Password-123456',
            account_type='organization',
            role='main_user',
            organization=self.organization,
        )
        self.other_manager = User.objects.create_user(
            username='settings-other-manager',
            password='Password-123456',
            account_type='organization',
            role='main_user',
            organization=self.other_organization,
        )
        self.branch_manager = User.objects.create_user(
            username='settings-branch-manager',
            password='Password-123456',
            account_type='organization',
            role='branch_manager',
            organization=self.organization,
        )
        self.detail_url = reverse('organization-detail', args=[self.organization.id])
        self.other_detail_url = reverse('organization-detail', args=[self.other_organization.id])

    def test_organization_manager_can_update_only_own_organization_details(self):
        self.client.force_authenticate(self.manager)
        response = self.client.patch(self.detail_url, {
            'name': 'نام جدید شرکت',
            'registration_number': '3003',
            'economy_code': '4004',
            'phone': '02122222222',
            'email': 'office@example.com',
            'website': 'https://example.com',
            'address': 'نشانی جدید',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.name, 'نام جدید شرکت')
        self.assertEqual(self.organization.registration_number, '3003')
        self.assertEqual(self.organization.economy_code, '4004')
        self.assertEqual(self.organization.phone, '02122222222')
        self.assertEqual(self.organization.email, 'office@example.com')
        self.assertEqual(self.organization.website, 'https://example.com')
        self.assertEqual(self.organization.address, 'نشانی جدید')

    def test_organization_manager_cannot_read_or_update_another_organization(self):
        self.client.force_authenticate(self.manager)
        response = self.client.patch(self.other_detail_url, {'name': 'غیرمجاز'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.other_organization.refresh_from_db()
        self.assertEqual(self.other_organization.name, 'شرکت دوم')

    def test_site_admin_can_update_selected_organization(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(self.other_detail_url, {'name': 'ویرایش ادمین'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.other_organization.refresh_from_db()
        self.assertEqual(self.other_organization.name, 'ویرایش ادمین')

    def test_branch_manager_cannot_update_organization(self):
        self.client.force_authenticate(self.branch_manager)
        response = self.client.patch(self.detail_url, {'name': 'تغییر غیرمجاز'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.name, 'شرکت اول')

    def test_organization_code_and_status_are_read_only_in_settings(self):
        self.client.force_authenticate(self.manager)
        response = self.client.patch(self.detail_url, {
            'name': 'نام مجاز',
            'code': 'CHANGED-CODE',
            'status': 'inactive',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.name, 'نام مجاز')
        self.assertEqual(self.organization.code, 'ORG-SETTINGS-01')
        self.assertEqual(self.organization.status, 'active')

    def test_unauthenticated_user_cannot_update_organization(self):
        response = self.client.patch(self.detail_url, {'name': 'بدون ورود'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.name, 'شرکت اول')
