from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from fleet.models import Driver
from organizations.models import Branch, Organization


class DriverMutationTenantSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization_a = Organization.objects.create(
            name='سازمان رانندگان الف',
            code='DRV-ORG-A',
        )
        self.organization_b = Organization.objects.create(
            name='سازمان رانندگان ب',
            code='DRV-ORG-B',
        )
        self.branch_a = Branch.objects.create(
            organization=self.organization_a,
            name='شعبه الف',
            code='DRV-BR-A',
        )
        self.branch_a2 = Branch.objects.create(
            organization=self.organization_a,
            name='شعبه دوم الف',
            code='DRV-BR-A2',
        )
        self.branch_b = Branch.objects.create(
            organization=self.organization_b,
            name='شعبه ب',
            code='DRV-BR-B',
        )
        self.personal_user = User.objects.create_user(
            username='driver-security-personal',
            password='test-password',
            account_type='personal',
            role='personal_user',
        )
        self.main_user = User.objects.create_user(
            username='driver-security-main',
            password='test-password',
            account_type='organization',
            role='main_user',
            organization=self.organization_a,
        )
        self.branch_manager = User.objects.create_user(
            username='driver-security-branch',
            password='test-password',
            account_type='organization',
            role='branch_manager',
            organization=self.organization_a,
            branch=self.branch_a,
        )
        self.own_driver = Driver.objects.create(
            organization=self.organization_a,
            branch=self.branch_a,
            first_name='راننده',
            last_name='خودمان',
            mobile='09120000001',
        )

    def payload(self, branch_id):
        return {
            'first_name': 'راننده',
            'last_name': 'جدید',
            'mobile': '09120000002',
            'branch': branch_id,
        }

    def test_personal_customer_cannot_create_a_driver(self):
        self.client.force_authenticate(user=self.personal_user)

        response = self.client.post(
            '/api/drivers/',
            self.payload(self.branch_a.id),
            format='json',
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Driver.objects.filter(mobile='09120000002').exists())

    def test_main_user_cannot_assign_driver_to_another_organizations_branch(self):
        self.client.force_authenticate(user=self.main_user)

        response = self.client.post(
            '/api/drivers/',
            self.payload(self.branch_b.id),
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Driver.objects.filter(mobile='09120000002').exists())

    def test_branch_manager_cannot_create_driver_in_another_branch(self):
        self.client.force_authenticate(user=self.branch_manager)

        response = self.client.post(
            '/api/drivers/',
            self.payload(self.branch_a2.id),
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Driver.objects.filter(mobile='09120000002').exists())

    def test_branch_manager_can_create_driver_in_own_branch(self):
        self.client.force_authenticate(user=self.branch_manager)

        response = self.client.post(
            '/api/drivers/',
            self.payload(self.branch_a.id),
            format='json',
        )

        self.assertEqual(response.status_code, 201, response.data)
        created = Driver.objects.get(mobile='09120000002')
        self.assertEqual(created.organization_id, self.organization_a.id)
        self.assertEqual(created.branch_id, self.branch_a.id)

    def test_branch_manager_cannot_move_existing_driver_to_another_branch(self):
        self.client.force_authenticate(user=self.branch_manager)

        response = self.client.patch(
            f'/api/drivers/{self.own_driver.id}/',
            {'branch': self.branch_a2.id},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.own_driver.refresh_from_db()
        self.assertEqual(self.own_driver.branch_id, self.branch_a.id)
