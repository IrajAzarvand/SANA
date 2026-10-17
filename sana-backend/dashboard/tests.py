from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from .models import SiteSettings


class SiteSettingsAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='settings_admin',
            password='test-password',
            role='site_admin',
            account_type='admin',
        )
        self.member = User.objects.create_user(
            username='settings_member',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )

    def test_authenticated_user_can_read_default_settings(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.get('/api/site-settings/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['map_provider'], 'leaflet-osm')
        self.assertEqual(response.data['map_refresh_interval_seconds'], 10)
        self.assertTrue(SiteSettings.objects.filter(pk=1).exists())

    def test_only_site_admin_can_change_settings(self):
        self.client.force_authenticate(user=self.member)
        denied = self.client.patch(
            '/api/site-settings/',
            {'map_provider': 'neshan-leaflet'},
            format='json',
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(user=self.admin)
        allowed = self.client.patch(
            '/api/site-settings/',
            {
                'map_provider': 'neshan-leaflet',
                'map_refresh_interval_seconds': 5,
            },
            format='json',
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.data['map_provider'], 'neshan-leaflet')
        self.assertEqual(allowed.data['map_refresh_interval_seconds'], 5)

    def test_rejects_out_of_range_refresh_interval(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(
            '/api/site-settings/',
            {'map_refresh_interval_seconds': 2},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            SiteSettings.objects.get(pk=1).map_refresh_interval_seconds,
            10,
        )
