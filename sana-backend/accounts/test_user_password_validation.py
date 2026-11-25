from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User


class UserCreationPasswordValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='password-policy-admin',
            password='Admin-Login-Pass-826!',
            role='site_admin',
            account_type='admin',
        )
        self.client.force_authenticate(self.admin)

    def test_user_creation_rejects_numeric_common_and_similar_passwords(self):
        invalid_credentials = [
            ('numeric-password-user', '12345678'),
            ('common-password-user', 'password'),
            ('similar-password-user', 'similarity-target'),
        ]
        for username, password in invalid_credentials:
            with self.subTest(username=username):
                response = self.client.post('/api/users/', {
                    'username': username,
                    'password': password,
                    'account_type': 'personal',
                    'role': 'personal_user',
                }, format='json')
                self.assertEqual(response.status_code, 400)
                self.assertIn('password', response.data)
                self.assertFalse(User.objects.filter(username=username).exists())

    def test_user_creation_accepts_a_strong_non_similar_password(self):
        response = self.client.post('/api/users/', {
            'username': 'fresh-account-user',
            'password': 'N0t-Common-Password!739',
            'account_type': 'personal',
            'role': 'personal_user',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        created = User.objects.get(username='fresh-account-user')
        self.assertTrue(created.check_password('N0t-Common-Password!739'))
