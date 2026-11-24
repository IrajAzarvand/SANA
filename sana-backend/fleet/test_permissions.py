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
        from organizations.models import Subscription, SubscriptionDevice
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
        today = timezone.localdate()
        subscription = Subscription.objects.create(
            contract_number='REPL-SCOPE-CONTRACT',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=5),
            status='active',
        )
        for device in (first, second):
            SubscriptionDevice.objects.create(
                subscription=subscription,
                device=device,
                start_date=subscription.start_date,
                end_date=subscription.end_date,
            )
            DeviceCustomerAccessPeriod.objects.create(
                device=device,
                organization=organization,
                branch=branch,
                subscription=subscription,
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
        from organizations.models import Organization, Subscription, SubscriptionDevice

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
        today = timezone.localdate()
        subscription = Subscription.objects.create(
            contract_number='COMP-REPL-SCOPE-CONTRACT',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=2),
            end_date=today + timedelta(days=30),
            status='active',
        )
        for device in (own_device, second_own_device):
            SubscriptionDevice.objects.create(
                subscription=subscription,
                device=device,
                start_date=subscription.start_date,
                end_date=subscription.end_date,
            )
            DeviceCustomerAccessPeriod.objects.create(
                device=device,
                organization=organization,
                subscription=subscription,
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
        from fleet.models import Device, DeviceCustomerAccessPeriod, DeviceBranchHistory
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
        subscription = Subscription.objects.create(
            contract_number='LEGACY-REPORT-CONTRACT',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=10),
            status='active',
        )
        history_link = SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=10),
        )
        SubscriptionDevice.objects.filter(pk=history_link.pk).update(
            assigned_at=now - timedelta(days=3),
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=organization,
            branch=branch,
            subscription=subscription,
            started_at=now - timedelta(days=2),
        )
        DeviceBranchHistory.objects.create(
            device=device,
            organization=organization,
            branch=branch,
            subscription=subscription,
            started_at=now - timedelta(days=2),
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


class BranchManagerVehicleAndDriverTenantScopeTests(TestCase):
    def test_branch_manager_lists_and_branch_counts_exclude_foreign_tenant_records(self):
        from datetime import timedelta
        from django.utils import timezone
        from rest_framework.test import APIClient
        from accounts.models import User
        from fleet.models import Device, DeviceCustomerAccessPeriod, Driver, Vehicle
        from organizations.models import Branch, Organization

        organization = Organization.objects.create(
            name='Scoped Branch Tenant',
            code='BR-TENANT-OWN',
        )
        other_organization = Organization.objects.create(
            name='Foreign Branch Tenant',
            code='BR-TENANT-OTHER',
        )
        branch = Branch.objects.create(
            organization=organization,
            name='Tenant Scoped Branch',
            code='BR-TENANT',
        )
        manager = User.objects.create_user(
            username='branch_tenant_scope_manager',
            password='test-password',
            role='branch_manager',
            account_type='organization',
            organization=organization,
            branch=branch,
        )
        own_vehicle = Vehicle.objects.create(
            plate='44الف444',
            organization=organization,
            branch=branch,
        )
        Vehicle.objects.create(
            plate='55ب555',
            organization=other_organization,
            branch=branch,
        )
        own_driver = Driver.objects.create(
            first_name='Own',
            last_name='Driver',
            mobile='09120000001',
            organization=organization,
            branch=branch,
        )
        Driver.objects.create(
            first_name='Foreign',
            last_name='Driver',
            mobile='09120000002',
            organization=other_organization,
            branch=branch,
        )
        unassigned_vehicle_device = Device.objects.create(
            imei='860000000000950',
            organization=organization,
            branch=branch,
            vehicle=own_vehicle,
        )
        device = Device.objects.create(
            imei='860000000000951',
            organization=organization,
            branch=branch,
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=organization,
            branch=branch,
            started_at=timezone.now() - timedelta(days=1),
        )

        client = APIClient()
        client.force_authenticate(user=manager)

        vehicles = client.get('/api/vehicles/')
        self.assertEqual(vehicles.status_code, 200)
        vehicle_payload = vehicles.data['results'] if isinstance(vehicles.data, dict) else vehicles.data
        self.assertEqual([item['id'] for item in vehicle_payload], [own_vehicle.id])
        self.assertEqual(vehicle_payload[0]['device_status'], 'none')

        drivers = client.get('/api/drivers/')
        self.assertEqual(drivers.status_code, 200)
        driver_payload = drivers.data['results'] if isinstance(drivers.data, dict) else drivers.data
        self.assertEqual([item['id'] for item in driver_payload], [own_driver.id])

        branch_detail = client.get(f'/api/branches/{branch.id}/')
        self.assertEqual(branch_detail.status_code, 200)
        self.assertEqual(branch_detail.data['vehicles_count'], 1)
        self.assertEqual(branch_detail.data['drivers_count'], 1)
        self.assertEqual(branch_detail.data['devices_count'], 1)
        self.assertIsNone(branch_detail.data['users_count'])


class DeviceListContractTenantScopeTests(TestCase):
    def test_company_device_list_does_not_embed_foreign_active_contract(self):
        from datetime import timedelta
        from unittest.mock import patch
        from django.utils import timezone
        from rest_framework.test import APIClient
        from accounts.models import User
        from fleet.models import Device, DeviceCustomerAccessPeriod
        from organizations.models import Organization, Subscription, SubscriptionDevice

        today = timezone.localdate()
        now = timezone.now()
        organization = Organization.objects.create(
            name='Device List Own Org',
            code='DEVICE-LIST-OWN',
        )
        other_organization = Organization.objects.create(
            name='Device List Foreign Org',
            code='DEVICE-LIST-FOREIGN',
        )
        manager = User.objects.create_user(
            username='device_list_tenant_manager',
            password='test-password',
            role='main_user',
            account_type='organization',
            organization=organization,
        )
        device = Device.objects.create(
            imei='860000000000981',
            organization=organization,
        )
        foreign_subscription = Subscription.objects.create(
            contract_number='FOREIGN-DEVICE-LIST-CONTRACT',
            customer_type='organization',
            organization=other_organization,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=5),
            status='active',
        )
        foreign_link = SubscriptionDevice.objects.create(
            subscription=foreign_subscription,
            device=device,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=5),
        )
        # Keep the foreign link as history; only the own contract is active.
        foreign_link.unassigned_at = now - timedelta(hours=1)
        foreign_link.save(update_fields=['unassigned_at'])
        own_subscription = Subscription.objects.create(
            contract_number='OWN-DEVICE-LIST-CONTRACT',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=5),
            status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=own_subscription,
            device=device,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=5),
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=organization,
            subscription=own_subscription,
            started_at=now - timedelta(days=1),
        )

        client = APIClient()
        client.force_authenticate(user=manager)
        with patch('fleet.views.traccar_devices', return_value=[]), patch(
            'fleet.views.traccar_current_positions',
            return_value=[],
        ):
            response = client.get('/api/devices/')

        self.assertEqual(response.status_code, 200)
        payload = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['subscription_id'], own_subscription.id)
        self.assertEqual(payload[0]['subscription_number'], own_subscription.contract_number)
        self.assertNotIn('FOREIGN-DEVICE-LIST-CONTRACT', str(payload[0]))


class BranchManagerReportHistoryPeriodFilterTests(TestCase):
    def test_history_points_are_filtered_to_branch_access_periods(self):
        from datetime import timedelta
        from unittest.mock import patch

        from django.utils import timezone
        from rest_framework.test import APIClient
        from accounts.models import User
        from fleet.models import Device, DeviceCustomerAccessPeriod, DeviceBranchHistory
        from organizations.models import Branch, Organization, Subscription, SubscriptionDevice

        now = timezone.now()
        today = timezone.localdate()
        organization = Organization.objects.create(name='History Filter Org', code='HIST-FILTER-ORG')
        branch_a = Branch.objects.create(organization=organization, name='History Branch A', code='HIST-A')
        branch_b = Branch.objects.create(organization=organization, name='History Branch B', code='HIST-B')
        manager = User.objects.create_user(
            username='history_filter_manager', password='test-password',
            role='branch_manager', account_type='organization', organization=organization, branch=branch_a,
        )
        device = Device.objects.create(imei='860000000000952', organization=organization, branch=branch_a)
        subscription = Subscription.objects.create(
            contract_number='HIST-FILTER-CONTRACT', customer_type='organization', organization=organization,
            start_date=today - timedelta(days=12), end_date=today + timedelta(days=12), status='active',
        )
        history_link = SubscriptionDevice.objects.create(
            subscription=subscription, device=device,
            start_date=today - timedelta(days=12), end_date=today + timedelta(days=12),
        )
        SubscriptionDevice.objects.filter(pk=history_link.pk).update(
            assigned_at=now - timedelta(days=12),
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device, organization=organization, branch=branch_a, subscription=subscription,
            started_at=now - timedelta(days=10), ended_at=now - timedelta(days=6),
        )
        DeviceBranchHistory.objects.create(
            device=device, organization=organization, branch=branch_a, subscription=subscription,
            started_at=now - timedelta(days=10), ended_at=now - timedelta(days=6),
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device, organization=organization, branch=branch_b, subscription=subscription,
            started_at=now - timedelta(days=5), ended_at=now - timedelta(days=1),
        )
        DeviceBranchHistory.objects.create(
            device=device, organization=organization, branch=branch_b, subscription=subscription,
            started_at=now - timedelta(days=5), ended_at=now - timedelta(days=1),
        )

        branch_a_time = (now - timedelta(days=8)).isoformat()
        branch_b_time = (now - timedelta(days=3)).isoformat()
        positions = [
            {'id': 1001, 'serverTime': branch_a_time, 'fixTime': branch_a_time,
             'latitude': 35.7, 'longitude': 51.4, 'speed': 0, 'course': 0, 'valid': True, 'attributes': {}},
            {'id': 1002, 'serverTime': branch_b_time, 'fixTime': branch_b_time,
             'latitude': 35.8, 'longitude': 51.5, 'speed': 0, 'course': 0, 'valid': True, 'attributes': {}},
        ]
        client = APIClient()
        client.force_authenticate(user=manager)
        with patch('fleet.views.traccar_history_device_id', return_value=77), \
             patch('fleet.views.traccar_device_positions', return_value=positions), \
             patch('fleet.views.connection.cursor') as map_matched_cursor:
            map_matched_cursor.return_value.__enter__.return_value.fetchall.return_value = []
            response = client.get('/api/devices/report-history/', {
                'device_id': device.id,
                'from': (now - timedelta(days=10)).isoformat(),
                'to': (now - timedelta(days=1)).isoformat(),
            })

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([point['id'] for point in response.data['points']], [1001])


class BranchManagerSuspensionHistoryTests(TestCase):
    def test_branch_history_remains_visible_during_suspension_gap(self):
        from datetime import timedelta
        from unittest.mock import patch
        from django.utils import timezone
        from rest_framework.test import APIClient
        from accounts.models import User
        from fleet.models import Device, DeviceCustomerAccessPeriod, DeviceBranchHistory
        from organizations.models import Branch, Organization, Subscription, SubscriptionDevice

        now = timezone.now()
        today = timezone.localdate()
        legal_owner = Organization.objects.create(name='Suspension History Legal Owner', code='SUSP-HIST-OWNER')
        customer = Organization.objects.create(name='Suspension History Customer', code='SUSP-HIST-CUSTOMER')
        branch = Branch.objects.create(organization=customer, name='Suspension History Branch', code='SUSP-HIST-BRANCH')
        manager = User.objects.create_user(
            username='suspension_history_branch_manager', password='test-password',
            role='branch_manager', account_type='organization', organization=customer, branch=branch,
        )
        device = Device.objects.create(
            imei='860000000000970', organization=legal_owner,
            current_holder_organization=customer, branch=branch,
        )
        subscription = Subscription.objects.create(
            contract_number='SUSPENSION-HISTORY-CONTRACT',
            customer_type='organization', organization=customer,
            start_date=today - timedelta(days=12), end_date=today + timedelta(days=12), status='suspended',
        )
        history_link = SubscriptionDevice.objects.create(
            subscription=subscription, device=device,
            start_date=today - timedelta(days=12), end_date=today + timedelta(days=12),
        )
        SubscriptionDevice.objects.filter(pk=history_link.pk).update(
            assigned_at=now - timedelta(days=12),
        )
        # Access periods close during suspension and reopen after it; branch assignment stays continuous.
        DeviceCustomerAccessPeriod.objects.create(
            device=device, organization=customer, branch=branch, subscription=subscription,
            started_at=now - timedelta(days=10), ended_at=now - timedelta(days=7),
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device, organization=customer, branch=branch, subscription=subscription,
            started_at=now - timedelta(days=4), ended_at=now - timedelta(days=1),
        )
        DeviceBranchHistory.objects.create(
            device=device, organization=customer, branch=branch, subscription=subscription,
            started_at=now - timedelta(days=10),
        )

        def point(point_id, days_ago):
            stamp = (now - timedelta(days=days_ago)).isoformat()
            return {
                'id': point_id, 'serverTime': stamp, 'fixTime': stamp,
                'latitude': 35.7 + point_id / 10000, 'longitude': 51.4,
                'speed': 0, 'course': 0, 'valid': True, 'attributes': {},
            }
        positions = [point(2001, 8), point(2002, 5), point(2003, 3)]
        client = APIClient()
        client.force_authenticate(user=manager)
        with patch('fleet.views.traccar_history_device_id', return_value=77), \
             patch('fleet.views.traccar_device_positions', return_value=positions), \
             patch('fleet.views.connection.cursor') as map_matched_cursor:
            map_matched_cursor.return_value.__enter__.return_value.fetchall.return_value = []
            response = client.get('/api/devices/report-history/', {
                'device_id': device.id,
                'from': (now - timedelta(days=10)).isoformat(),
                'to': (now - timedelta(days=1)).isoformat(),
            })

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([point['id'] for point in response.data['points']], [2001, 2002, 2003])

class BranchManagerExpiredRenewalHistoryTests(TestCase):
    def test_history_excludes_expired_gap_across_multiple_links_for_same_contract(self):
        from datetime import datetime, timedelta
        from unittest.mock import patch
        from django.utils import timezone
        from rest_framework.test import APIClient
        from accounts.models import User
        from fleet.models import Device, DeviceCustomerAccessPeriod, DeviceBranchHistory
        from organizations.models import Branch, Organization, Subscription, SubscriptionDevice

        now = timezone.now()
        today = timezone.localdate()
        old_end_date = today - timedelta(days=5)
        contract_start = old_end_date - timedelta(days=30)
        new_end_date = today + timedelta(days=30)
        old_assigned_at = now - timedelta(days=20)
        expiration_cutoff = timezone.make_aware(
            datetime.combine(old_end_date + timedelta(days=1), datetime.min.time()),
            timezone.get_current_timezone(),
        )
        renewal_time = now - timedelta(hours=2)

        organization = Organization.objects.create(
            name='Expired Renewal History Org',
            code='EXPIRED-RENEWAL-HISTORY-ORG',
        )
        branch = Branch.objects.create(
            organization=organization,
            name='Expired Renewal History Branch',
            code='EXPIRED-RENEWAL-HISTORY-BRANCH',
        )
        manager = User.objects.create_user(
            username='expired_renewal_history_manager',
            password='test-password',
            role='branch_manager',
            account_type='organization',
            organization=organization,
            branch=branch,
        )
        device = Device.objects.create(
            imei='860000000000977',
            organization=organization,
            current_holder_organization=organization,
            branch=branch,
            management_status='installed',
        )
        subscription = Subscription.objects.create(
            contract_number='EXPIRED-RENEWAL-HISTORY-CONTRACT',
            customer_type='organization',
            organization=organization,
            start_date=contract_start,
            end_date=new_end_date,
            status='active',
        )
        old_link = SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=contract_start,
            end_date=old_end_date,
        )
        SubscriptionDevice.objects.filter(pk=old_link.pk).update(
            assigned_at=old_assigned_at,
            unassigned_at=expiration_cutoff,
        )
        new_link = SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=today,
            end_date=new_end_date,
        )
        SubscriptionDevice.objects.filter(pk=new_link.pk).update(
            assigned_at=renewal_time,
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=organization,
            branch=branch,
            subscription=subscription,
            started_at=old_assigned_at,
            ended_at=expiration_cutoff,
            reason='contract_expired',
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=organization,
            branch=branch,
            subscription=subscription,
            started_at=renewal_time,
        )
        DeviceBranchHistory.objects.create(
            device=device,
            organization=organization,
            branch=branch,
            subscription=subscription,
            started_at=old_assigned_at,
        )

        before_expiry = expiration_cutoff - timedelta(hours=1)
        during_gap = expiration_cutoff + (renewal_time - expiration_cutoff) / 2
        after_renewal = renewal_time + timedelta(hours=1)

        def point(point_id, stamp):
            value = stamp.isoformat()
            return {
                'id': point_id,
                'serverTime': value,
                'fixTime': value,
                'latitude': 35.7 + point_id / 10000,
                'longitude': 51.4,
                'speed': 0,
                'course': 0,
                'valid': True,
                'attributes': {},
            }

        positions = [
            point(3001, before_expiry),
            point(3002, during_gap),
            point(3003, after_renewal),
        ]
        client = APIClient()
        client.force_authenticate(user=manager)
        with patch('fleet.views.traccar_history_device_id', return_value=77), \
             patch('fleet.views.traccar_device_positions', return_value=positions), \
             patch('fleet.views.connection.cursor') as map_matched_cursor:
            map_matched_cursor.return_value.__enter__.return_value.fetchall.return_value = []
            response = client.get('/api/devices/report-history/', {
                'device_id': device.id,
                'from': (old_assigned_at + timedelta(minutes=1)).isoformat(),
                'to': after_renewal.isoformat(),
            })

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item['id'] for item in response.data['points']], [3001, 3003])

