from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsMainUserOrSiteAdmin, IsOrganizationMember, IsSiteAdmin
from fleet.views import (
    DeviceLifecycleEventViewSet,
    DeviceOperationViewSet,
    DeviceReplacementRelationViewSet,
    DeviceViewSet,
    DriverVehicleAssignmentViewSet,
    VehicleTypeViewSet,
    VehicleViewSet,
)


class DeviceManagementPermissionTests(SimpleTestCase):
    def assert_mutations_require_site_admin(self, view_class, actions=None):
        actions = actions or ("create", "update", "partial_update", "destroy")
        for action in actions:
            with self.subTest(view=view_class.__name__, action=action):
                view = view_class()
                view.action = action
                permissions = view.get_permissions()
                self.assertIsInstance(permissions[0], IsSiteAdmin)

    def assert_mutations_require_company_manager_or_site_admin(self, view_class, actions=None):
        actions = actions or ("create", "update", "partial_update", "destroy")
        for action in actions:
            with self.subTest(view=view_class.__name__, action=action):
                view = view_class()
                view.action = action
                permissions = view.get_permissions()
                self.assertIsInstance(permissions[0], IsMainUserOrSiteAdmin)

    def test_vehicle_type_mutations_allow_company_manager_or_site_admin(self):
        self.assert_mutations_require_company_manager_or_site_admin(VehicleTypeViewSet)

    def test_vehicle_mutations_allow_company_manager_or_site_admin(self):
        self.assert_mutations_require_company_manager_or_site_admin(VehicleViewSet)

    def test_device_mutations_require_site_admin(self):
        self.assert_mutations_require_site_admin(DeviceViewSet)

    def test_device_history_and_replacement_mutations_require_site_admin(self):
        self.assert_mutations_require_site_admin(DeviceLifecycleEventViewSet)
        self.assert_mutations_require_site_admin(DeviceReplacementRelationViewSet)

    def test_device_operation_creation_requires_site_admin(self):
        self.assert_mutations_require_site_admin(DeviceOperationViewSet, ("create",))

    def test_device_listing_still_requires_authentication(self):
        view = DeviceViewSet()
        view.action = "list"
        self.assertIsInstance(view.get_permissions()[0], IsAuthenticated)

    def test_live_map_positions_require_authentication(self):
        view = DeviceViewSet()
        view.action = "map_positions"
        self.assertIsInstance(view.get_permissions()[0], IsAuthenticated)

    def test_site_admin_is_allowed_through_organization_member_permission(self):
        admin = SimpleNamespace(is_authenticated=True, is_site_admin=True, account_type='admin')
        request = SimpleNamespace(user=admin, method='POST')
        self.assertTrue(IsOrganizationMember().has_permission(request, None))

    def test_personal_user_is_not_allowed_through_organization_member_permission(self):
        personal = SimpleNamespace(is_authenticated=True, is_site_admin=False, account_type='personal')
        request = SimpleNamespace(user=personal, method='POST')
        self.assertFalse(IsOrganizationMember().has_permission(request, None))

class BranchManagerReplacementHistoryScopeTests(TestCase):
    def test_replacement_history_requires_active_access_to_both_devices(self):
        from datetime import timedelta
        from types import SimpleNamespace

        from django.utils import timezone
        from organizations.models import Organization, Branch
        from fleet.models import Device, DeviceCustomerAccessPeriod, DeviceReplacementRelation
        from accounts.models import User

        organization = Organization.objects.create(
            name='Replacement Scope Org',
            code='REPL-SCOPE-ORG',
        )
        branch = Branch.objects.create(
            organization=organization,
            name='Replacement Scope Branch',
            code='REPL-SCOPE',
        )
        manager = User.objects.create_user(
            username='replacement_scope_manager',
            password='test-password',
            role='branch_manager',
            account_type='organization',
            organization=organization,
            branch=branch,
        )
        first = Device.objects.create(imei='860000000000911', organization=organization, branch=branch)
        second = Device.objects.create(imei='860000000000912', organization=organization, branch=branch)
        no_longer_assigned = Device.objects.create(
            imei='860000000000913',
            organization=organization,
            branch=branch,
        )
        now = timezone.now()
        for device in (first, second):
            DeviceCustomerAccessPeriod.objects.create(
                device=device,
                organization=organization,
                branch=branch,
                started_at=now - timedelta(days=1),
            )
        visible = DeviceReplacementRelation.objects.create(
            source_device=first,
            replacement_device=second,
            replacement_type='temporary_repair',
        )
        hidden = DeviceReplacementRelation.objects.create(
            source_device=no_longer_assigned,
            replacement_device=second,
            replacement_type='temporary_repair',
        )

        view = DeviceReplacementRelationViewSet()
        view.request = SimpleNamespace(user=manager, query_params={})
        visible_ids = set(view.get_queryset().values_list('id', flat=True))
        self.assertIn(visible.id, visible_ids)
        self.assertNotIn(hidden.id, visible_ids)

        # The device list embeds the replacement device IMEI as a convenience
        # field, so its nested prefetch must enforce the same two-sided scope.
        device_view = DeviceViewSet()
        device_view.request = SimpleNamespace(user=manager, query_params={})
        device_view.action = 'list'
        listed_devices = list(device_view.get_queryset())
        listed_own_device = next(item for item in listed_devices if item.pk == first.pk)
        prefetched_relations = listed_own_device._replacement_relations_as_source
        self.assertEqual([item.pk for item in prefetched_relations], [visible.pk])

    def test_company_manager_cannot_see_replacement_of_external_device(self):
        from datetime import timedelta
        from types import SimpleNamespace

        from django.utils import timezone
        from accounts.models import User
        from fleet.models import Device, DeviceCustomerAccessPeriod, DeviceReplacementRelation
        from organizations.models import Organization

        organization = Organization.objects.create(
            name='Company Replacement Scope',
            code='COMP-REPL-SCOPE',
        )
        other = Organization.objects.create(
            name='External Replacement Scope',
            code='EXT-REPL-SCOPE',
        )
        manager = User.objects.create_user(
            username='company_replacement_scope',
            password='test-password',
            role='main_user',
            account_type='organization',
            organization=organization,
        )
        own_device = Device.objects.create(
            imei='860000000000921',
            organization=organization,
        )
        second_own_device = Device.objects.create(
            imei='860000000000923',
            organization=organization,
        )
        external_device = Device.objects.create(
            imei='860000000000922',
            organization=other,
        )
        now = timezone.now()
        for device in (own_device, second_own_device):
            DeviceCustomerAccessPeriod.objects.create(
                device=device,
                organization=organization,
                started_at=now - timedelta(days=1),
            )
        visible = DeviceReplacementRelation.objects.create(
            source_device=own_device,
            replacement_device=second_own_device,
            replacement_type='temporary_repair',
        )
        hidden = DeviceReplacementRelation.objects.create(
            source_device=own_device,
            replacement_device=external_device,
            replacement_type='temporary_repair',
        )

        view = DeviceReplacementRelationViewSet()
        view.request = SimpleNamespace(user=manager, query_params={})
        visible_ids = set(view.get_queryset().values_list('id', flat=True))
        self.assertIn(visible.id, visible_ids)
        self.assertNotIn(hidden.id, visible_ids)


class DriverVehicleAssignmentReadScopeTests(TestCase):
    def test_branch_manager_assignment_history_requires_both_records_in_branch(self):
        from datetime import timedelta
        from types import SimpleNamespace

        from django.utils import timezone
        from accounts.models import User
        from fleet.models import Driver, DriverVehicleAssignment, Vehicle
        from organizations.models import Branch, Organization

        organization = Organization.objects.create(
            name='Assignment Scope Org',
            code='ASSIGN-SCOPE-ORG',
        )
        other_organization = Organization.objects.create(
            name='Assignment Other Org',
            code='ASSIGN-OTHER-ORG',
        )
        branch = Branch.objects.create(
            organization=organization,
            name='Assignment Scope Branch',
            code='ASSIGN-SCOPE',
        )
        other_branch = Branch.objects.create(
            organization=organization,
            name='Assignment Other Branch',
            code='ASSIGN-OTHER',
        )
        manager = User.objects.create_user(
            username='assignment_scope_manager',
            password='test-password',
            role='branch_manager',
            account_type='organization',
            organization=organization,
            branch=branch,
        )
        driver = Driver.objects.create(
            first_name='Branch',
            last_name='Driver',
            mobile='09120000000',
            organization=organization,
            branch=branch,
        )
        own_vehicle = Vehicle.objects.create(
            plate='11الف111',
            organization=organization,
            branch=branch,
        )
        other_branch_vehicle = Vehicle.objects.create(
            plate='22ب222',
            organization=organization,
            branch=other_branch,
        )
        external_vehicle = Vehicle.objects.create(
            plate='33ج333',
            organization=other_organization,
        )
        now = timezone.now()
        visible = DriverVehicleAssignment.objects.create(
            driver=driver,
            vehicle=own_vehicle,
            started_at=now - timedelta(days=2),
        )
        hidden_branch = DriverVehicleAssignment.objects.create(
            driver=driver,
            vehicle=other_branch_vehicle,
            started_at=now - timedelta(days=1),
        )
        hidden_external = DriverVehicleAssignment.objects.create(
            driver=driver,
            vehicle=external_vehicle,
            started_at=now,
        )

        view = DriverVehicleAssignmentViewSet()
        view.request = SimpleNamespace(user=manager, query_params={})
        visible_ids = set(view.get_queryset().values_list('id', flat=True))
        self.assertIn(visible.pk, visible_ids)
        self.assertNotIn(hidden_branch.pk, visible_ids)
        self.assertNotIn(hidden_external.pk, visible_ids)


class LegacyBranchManagerReportHistoryScopeTests(TestCase):
    def test_report_history_uses_branch_organization_when_user_organization_is_null(self):
        from datetime import timedelta

        from django.utils import timezone
        from rest_framework.test import APIClient
        from accounts.models import User
        from fleet.models import Device, DeviceCustomerAccessPeriod
        from organizations.models import Branch, Organization, Subscription, SubscriptionDevice

        today = timezone.localdate()
        now = timezone.now()
        organization = Organization.objects.create(
            name='Legacy Report Org',
            code='LEGACY-REPORT-ORG',
        )
        branch = Branch.objects.create(
            organization=organization,
            name='Legacy Report Branch',
            code='LEGACY-REPORT',
        )
        manager = User.objects.create_user(
            username='legacy_report_branch_manager',
            password='test-password',
            role='branch_manager',
            account_type='organization',
            branch=branch,
        )
        device = Device.objects.create(
            imei='860000000000941',
            organization=organization,
            branch=branch,
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=organization,
            branch=branch,
            started_at=now - timedelta(days=2),
        )
        subscription = Subscription.objects.create(
            contract_number='LEGACY-REPORT-CONTRACT',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=10),
            status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=10),
        )

        client = APIClient()
        client.force_authenticate(user=manager)
        response = client.get(
            '/api/devices/report-history/',
            {'device_id': device.id, 'metadata': 'true'},
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['device']['id'], device.id)
        self.assertFalse(response.data['unrestricted'])
        self.assertIsNotNone(response.data['range_start'])
        self.assertIsNotNone(response.data['range_end'])


class BranchManagerVehicleTypeScopeTests(TestCase):
    def test_legacy_branch_manager_sees_only_branch_organization_vehicle_types_without_org_id(self):
        from rest_framework.test import APIClient
        from fleet.models import VehicleType
        from accounts.models import User
        from organizations.models import Branch, Organization

        organization = Organization.objects.create(
            name='Vehicle Type Scope Org',
            code='VT-SCOPE-ORG',
        )
        other_organization = Organization.objects.create(
            name='Other Vehicle Type Scope Org',
            code='VT-OTHER-ORG',
        )
        branch = Branch.objects.create(
            organization=organization,
            name='Vehicle Type Scope Branch',
            code='VT-SCOPE',
        )
        manager = User.objects.create_user(
            username='vehicle_type_legacy_manager',
            password='test-password',
            role='branch_manager',
            account_type='organization',
            branch=branch,
        )
        own_type = VehicleType.objects.create(name='Branch Bus', organization=organization)
        VehicleType.objects.create(name='External Truck', organization=other_organization)

        client = APIClient()
        client.force_authenticate(user=manager)
        response = client.get('/api/vehicle-types/')

        self.assertEqual(response.status_code, 200)
        payload = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertEqual([item['id'] for item in payload], [own_type.id])
        self.assertIsNone(payload[0]['organization'])
