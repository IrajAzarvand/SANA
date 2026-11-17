from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from fleet.models import Device
from fleet.views import DeviceViewSet
from organizations.models import Subscription, SubscriptionDevice


class PersonalDeviceContractBoundsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='personal-device-contract-bounds',
            password='test-password',
            account_type='personal',
            role='personal_user',
        )
        self.today = timezone.localdate()

    def add_device_with_mismatched_parent_contract(self, *, imei, start_date, end_date):
        device = Device.objects.create(
            imei=imei,
            management_status='sold',
        )
        subscription = Subscription.objects.create(
            contract_number=f'CONTRACT-BOUNDS-{imei[-4:]}',
            customer_type='personal',
            user=self.user,
            start_date=start_date,
            end_date=end_date,
            status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=self.today - timedelta(days=5),
            end_date=self.today + timedelta(days=30),
        )
        return device

    def test_device_link_cannot_extend_access_beyond_parent_contract_dates(self):
        expired = self.add_device_with_mismatched_parent_contract(
            imei='860000000000401',
            start_date=self.today - timedelta(days=30),
            end_date=self.today - timedelta(days=1),
        )
        not_started = self.add_device_with_mismatched_parent_contract(
            imei='860000000000402',
            start_date=self.today + timedelta(days=1),
            end_date=self.today + timedelta(days=30),
        )

        request = APIRequestFactory().get('/api/devices/')
        force_authenticate(request, user=self.user)
        view = DeviceViewSet()
        view.action_map = {'get': 'list'}
        view.request = view.initialize_request(request)

        visible_ids = set(view.get_queryset().values_list('id', flat=True))

        self.assertNotIn(expired.id, visible_ids)
        self.assertNotIn(not_started.id, visible_ids)
