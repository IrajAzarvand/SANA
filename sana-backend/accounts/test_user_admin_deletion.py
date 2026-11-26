from django.test import TestCase, RequestFactory
from django.contrib import admin as django_admin

from accounts.models import User
from accounts.admin import UserAdmin


class UserAdminDeletionPolicyTests(TestCase):
    def test_django_admin_disables_physical_user_deletion(self):
        request = RequestFactory().get('/admin/accounts/user/')
        request.user = User.objects.create_user(
            username='delete-policy-admin',
            password='Admin-Password-829!',
            role='site_admin',
            account_type='admin',
        )
        model_admin = UserAdmin(User, django_admin.site)
        self.assertFalse(model_admin.has_delete_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request, request.user))
