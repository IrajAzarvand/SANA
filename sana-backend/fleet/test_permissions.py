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
        from organizations.models import Organization, Branch, Subscription, SubscriptionDevice
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
        today = timezone.localdate()
        for index, device in enumerate((first, second), start=1):
            subscription = Subscription.objects.create(
                contract_number=f'REPL-SCOPE-{index}',
                customer_type='organization',
                organization=organization,
                start_date=today - timedelta(days=5),
                end_date=today + timedelta(days=30),
                status='active',
            )
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
        for index, device in enumerate((own_device, second_own_device), start=1):
            subscription = Subscription.objects.create(
                contract_number=f'COMP-REPL-SCOPE-{index}',
                customer_type='organization',
                organization=organization,
                start_date=today - timedelta(days=5),
                end_date=today + timedelta(days=30),
                status='active',
            )
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
        subscription = Subscription.objects.create(
            contract_number='LEGACY-REPORT-CONTRACT',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=10),
            status='active',
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=organization,
            branch=branch,
            subscription=subscription,
            started_at=now - timedelta(days=2),
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


class BranchManagerVehicleAndDriverTenantScopeTests(TestCase):
    def test_branch_manager_lists_and_branch_counts_exclude_foreign_tenant_records(self):
        from datetime import timedelta
        from django.utils import timezone
        from rest_framework.test import APIClient
        from accounts.models import User
        from fleet.models import Device, DeviceCustomerAccessPeriod, Driver, Vehicle
        from organizations.models import Branch, Organization, Subscription, SubscriptionDevice

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
        today = timezone.localdate()
        subscription = Subscription.objects.create(
            contract_number='BRANCH-TENANT-ACCESS',
            customer_type='organization',
            organization=organization,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=30),
            status='active',
        )
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
        SubscriptionDevice.objects.create(
            subscription=foreign_subscription,
            device=device,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=5),
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device,
            organization=organization,
            subscription=foreign_subscription,
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
        self.assertEqual(payload, [])
        self.assertNotIn('FOREIGN-DEVICE-LIST-CONTRACT', str(payload))


class PersonalReplacementHistoryFutureAssignmentTests(TestCase):
    def test_future_assigned_device_does_not_authorize_replacement_history(self):
        from datetime import timedelta

        from django.utils import timezone
        from accounts.models import User
        from organizations.models import Subscription, SubscriptionDevice
        from fleet.models import Device, DeviceReplacementRelation

        user = User.objects.create_user(
            username='personal_future_replacement_history',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        today = timezone.localdate()
        now = timezone.now()
        future_device = Device.objects.create(imei='860000000001401')
        current_device = Device.objects.create(imei='860000000001402')
        future_subscription = Subscription.objects.create(
            contract_number='PERSONAL-FUTURE-REPL-001',
            customer_type='personal',
            user=user,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=20),
            status='active',
        )
        current_subscription = Subscription.objects.create(
            contract_number='PERSONAL-CURRENT-REPL-001',
            customer_type='personal',
            user=user,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=20),
            status='active',
        )
        future_link = SubscriptionDevice.objects.create(
            subscription=future_subscription,
            device=future_device,
            start_date=future_subscription.start_date,
            end_date=future_subscription.end_date,
        )
        SubscriptionDevice.objects.filter(pk=future_link.pk).update(
            assigned_at=now + timedelta(minutes=10)
        )
        SubscriptionDevice.objects.create(
            subscription=current_subscription,
            device=current_device,
            start_date=current_subscription.start_date,
            end_date=current_subscription.end_date,
        )
        relation = DeviceReplacementRelation.objects.create(
            source_device=future_device,
            replacement_device=current_device,
            replacement_type='temporary_repair',
        )

        view = DeviceReplacementRelationViewSet()
        view.request = SimpleNamespace(user=user, query_params={})

        self.assertNotIn(
            relation.pk,
            set(view.get_queryset().values_list('id', flat=True)),
        )


class VehicleDeviceDisclosureScopeTests(TestCase):
    def test_company_vehicle_detail_hides_device_without_current_customer_access(self):
        from datetime import timedelta
        from django.utils import timezone
        from rest_framework.test import APIClient
        from accounts.models import User
        from fleet.models import Device, Vehicle
        from organizations.models import Organization, Subscription, SubscriptionDevice
        from fleet.models import DeviceCustomerAccessPeriod

        today = timezone.localdate()
        own_org = Organization.objects.create(name='Vehicle Owner Org', code='VEH-OWNER-ORG')
        other_org = Organization.objects.create(name='Vehicle Device Org', code='VEH-DEVICE-ORG')
        manager = User.objects.create_user(
            username='vehicle_device_scope_manager', password='test-password',
            role='main_user', account_type='organization', organization=own_org,
        )
        vehicle = Vehicle.objects.create(plate='77الف777', organization=own_org)
        device = Device.objects.create(
            imei='860000000009701', organization=other_org, vehicle=vehicle,
            management_status='active',
        )
        foreign_contract = Subscription.objects.create(
            contract_number='VEHICLE-FOREIGN-CONTRACT', customer_type='organization',
            organization=other_org, start_date=today-timedelta(days=2),
            end_date=today+timedelta(days=20), status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=foreign_contract, device=device,
            start_date=foreign_contract.start_date, end_date=foreign_contract.end_date,
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device, organization=other_org, subscription=foreign_contract,
            started_at=timezone.now()-timedelta(days=1),
        )

        client = APIClient()
        client.force_authenticate(user=manager)
        detail = client.get(f'/api/vehicles/{vehicle.pk}/')
        listing = client.get('/api/vehicles/')

        self.assertEqual(detail.status_code, 200)
        self.assertIsNone(detail.data['device_imei'])
        self.assertEqual(listing.status_code, 200)
        rows = listing.data['results'] if isinstance(listing.data, dict) else listing.data
        self.assertEqual(rows[0]['device_status'], 'none')
        self.assertNotIn(device.imei, str(detail.data))
        self.assertNotIn(device.imei, str(rows))

    def test_company_vehicle_detail_shows_device_with_current_customer_access(self):
        from datetime import timedelta
        from django.utils import timezone
        from rest_framework.test import APIClient
        from accounts.models import User
        from fleet.models import Device, DeviceCustomerAccessPeriod, Vehicle
        from organizations.models import Organization, Subscription, SubscriptionDevice

        today = timezone.localdate()
        organization = Organization.objects.create(name='Vehicle Authorized Org', code='VEH-AUTH-ORG')
        manager = User.objects.create_user(
            username='vehicle_device_authorized_manager', password='test-password',
            role='main_user', account_type='organization', organization=organization,
        )
        vehicle = Vehicle.objects.create(plate='88ب888', organization=organization)
        device = Device.objects.create(
            imei='860000000009702', organization=organization, vehicle=vehicle,
            management_status='active',
        )
        contract = Subscription.objects.create(
            contract_number='VEHICLE-AUTH-CONTRACT', customer_type='organization',
            organization=organization, start_date=today-timedelta(days=2),
            end_date=today+timedelta(days=20), status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=contract, device=device,
            start_date=contract.start_date, end_date=contract.end_date,
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device, organization=organization, subscription=contract,
            started_at=timezone.now()-timedelta(days=1),
        )

        client = APIClient()
        client.force_authenticate(user=manager)
        response = client.get(f'/api/vehicles/{vehicle.pk}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['device_imei'], device.imei)


class DevicePartyMetadataDisclosureTests(TestCase):
    def test_company_customer_cannot_see_foreign_legal_owner_or_vehicle(self):
        from datetime import timedelta
        from unittest.mock import patch
        from django.utils import timezone
        from rest_framework.test import APIClient
        from accounts.models import User
        from fleet.models import Device, DeviceCustomerAccessPeriod, Vehicle
        from organizations.models import Organization, Subscription, SubscriptionDevice

        today = timezone.localdate()
        own_org = Organization.objects.create(name='Device Holder Org', code='DEVICE-HOLDER-ORG')
        legal_owner = Organization.objects.create(name='Device Legal Owner Org', code='DEVICE-LEGAL-OWNER')
        manager = User.objects.create_user(
            username='device_party_company_manager', password='test-password',
            role='main_user', account_type='organization', organization=own_org,
        )
        foreign_vehicle = Vehicle.objects.create(
            plate='66د666', organization=legal_owner,
        )
        device = Device.objects.create(
            imei='860000000009911', organization=legal_owner,
            current_holder_organization=own_org, vehicle=foreign_vehicle,
            management_status='active',
        )
        contract = Subscription.objects.create(
            contract_number='DEVICE-PARTY-CURRENT', customer_type='organization',
            organization=own_org, start_date=today-timedelta(days=3),
            end_date=today+timedelta(days=20), status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=contract, device=device,
            start_date=contract.start_date, end_date=contract.end_date,
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device, organization=own_org, subscription=contract,
            started_at=timezone.now()-timedelta(days=1),
        )

        client = APIClient()
        client.force_authenticate(user=manager)
        detail = client.get(f'/api/devices/{device.pk}/')
        with patch('fleet.views.traccar_devices', return_value=[]), patch(
            'fleet.views.traccar_current_positions', return_value=[],
        ):
            listing = client.get('/api/devices/')

        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertIsNone(detail.data['organization'])
        self.assertIsNone(detail.data['organization_name'])
        self.assertIsNone(detail.data['owner_user'])
        self.assertIsNone(detail.data.get('owner_name'))
        self.assertIsNone(detail.data['vehicle'])
        self.assertIsNone(detail.data['vehicle_plate'])
        self.assertEqual(detail.data['current_holder_organization'], own_org.pk)
        self.assertEqual(detail.data['current_holder_organization_name'], own_org.name)

        self.assertEqual(listing.status_code, 200, listing.data)
        rows = listing.data['results'] if isinstance(listing.data, dict) else listing.data
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]['organization'])
        self.assertIsNone(rows[0]['organization_name'])
        self.assertIsNone(rows[0]['owner_user'])
        self.assertIsNone(rows[0].get('owner_name'))
        self.assertIsNone(rows[0]['vehicle_plate'])

    def test_personal_customer_cannot_see_another_persons_legal_ownership(self):
        from datetime import timedelta
        from django.utils import timezone
        from rest_framework.test import APIClient
        from accounts.models import User
        from fleet.models import Device, Vehicle
        from organizations.models import Subscription, SubscriptionDevice

        user = User.objects.create_user(
            username='device_party_personal_customer', password='test-password',
            role='personal_user', account_type='personal', first_name='Personal', last_name='Customer',
        )
        other_owner = User.objects.create_user(
            username='device_party_other_owner', password='test-password',
            role='personal_user', account_type='personal', first_name='Other', last_name='Owner',
        )
        today = timezone.localdate()
        foreign_vehicle = Vehicle.objects.create(plate='55ه555', owner_user=other_owner)
        device = Device.objects.create(
            imei='860000000009912', owner_user=other_owner,
            current_holder_user=user, vehicle=foreign_vehicle,
            management_status='active',
        )
        contract = Subscription.objects.create(
            contract_number='DEVICE-PARTY-PERSONAL', customer_type='personal',
            user=user, start_date=today-timedelta(days=3),
            end_date=today+timedelta(days=20), status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=contract, device=device,
            start_date=contract.start_date, end_date=contract.end_date,
        )

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get(f'/api/devices/{device.pk}/')

        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data['owner_user'])
        self.assertIsNone(response.data.get('owner_name'))
        self.assertIsNone(response.data['vehicle'])
        self.assertIsNone(response.data['vehicle_plate'])
        self.assertEqual(response.data['current_holder_user'], user.pk)
        self.assertEqual(response.data['current_holder_user_name'], user.full_name)


class LegacyBranchManagerDeviceMetadataTests(TestCase):
    def test_legacy_branch_manager_keeps_own_branch_and_vehicle_labels(self):
        from datetime import timedelta
        from unittest.mock import patch
        from django.utils import timezone
        from rest_framework.test import APIClient
        from accounts.models import User
        from fleet.models import Device, DeviceCustomerAccessPeriod, Vehicle
        from organizations.models import Branch, Organization, Subscription, SubscriptionDevice

        today = timezone.localdate()
        organization = Organization.objects.create(
            name='Legacy Branch Device Metadata', code='LEGACY-BR-DEVICE-META',
        )
        branch = Branch.objects.create(
            organization=organization, name='Legacy Metadata Branch',
            code='LEGACY-META-BR',
        )
        manager = User.objects.create_user(
            username='legacy_branch_device_metadata', password='test-password',
            role='branch_manager', account_type='organization', branch=branch,
        )
        vehicle = Vehicle.objects.create(
            plate='44ز444', organization=organization, branch=branch,
        )
        device = Device.objects.create(
            imei='860000000009941', organization=organization, branch=branch,
            vehicle=vehicle, current_holder_organization=organization,
            management_status='active',
        )
        contract = Subscription.objects.create(
            contract_number='LEGACY-BR-DEVICE-META', customer_type='organization',
            organization=organization, start_date=today-timedelta(days=3),
            end_date=today+timedelta(days=20), status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=contract, device=device,
            start_date=contract.start_date, end_date=contract.end_date,
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device, organization=organization, branch=branch,
            subscription=contract, started_at=timezone.now()-timedelta(days=1),
        )

        client = APIClient()
        client.force_authenticate(user=manager)
        with patch('fleet.views.traccar_devices', return_value=[]), patch(
            'fleet.views.traccar_current_positions', return_value=[],
        ):
            response = client.get('/api/devices/')

        self.assertEqual(response.status_code, 200, response.data)
        rows = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['branch_name'], branch.name)
        self.assertEqual(rows[0]['vehicle_plate'], vehicle.plate)


class DeviceModelCountTenantScopeTests(TestCase):
    def test_customer_sees_only_count_of_devices_in_their_authorized_scope(self):
        from datetime import timedelta
        from django.utils import timezone
        from rest_framework.test import APIClient
        from accounts.models import User
        from fleet.models import Device, DeviceCustomerAccessPeriod, DeviceModel
        from organizations.models import Organization, Subscription, SubscriptionDevice

        today = timezone.localdate()
        model = DeviceModel.objects.create(
            manufacturer='Count Scope', name='Shared Model', code='COUNT-SCOPE',
            protocol='gt06', is_verified=True,
        )
        organization = Organization.objects.create(
            name='Count Scope Org', code='COUNT-SCOPE-ORG',
        )
        other_organization = Organization.objects.create(
            name='Count Scope Other Org', code='COUNT-SCOPE-OTHER',
        )
        manager = User.objects.create_user(
            username='device_model_count_manager', password='test-password',
            role='main_user', account_type='organization', organization=organization,
        )
        own_device = Device.objects.create(
            imei='860000000009921', organization=organization, device_model=model,
        )
        Device.objects.create(
            imei='860000000009922', organization=other_organization, device_model=model,
        )
        contract = Subscription.objects.create(
            contract_number='DEVICE-MODEL-COUNT', customer_type='organization',
            organization=organization, start_date=today-timedelta(days=2),
            end_date=today+timedelta(days=20), status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=contract, device=own_device,
            start_date=contract.start_date, end_date=contract.end_date,
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=own_device, organization=organization, subscription=contract,
            started_at=timezone.now()-timedelta(days=1),
        )

        client = APIClient()
        client.force_authenticate(user=manager)
        response = client.get('/api/device-models/')

        self.assertEqual(response.status_code, 200, response.data)
        payload = response.data['results'] if isinstance(response.data, dict) else response.data
        row = next(item for item in payload if item['id'] == model.pk)
        self.assertEqual(row['devices_count'], 1)


class ReportHistoryDateUpperBoundTests(TestCase):
    def test_personal_report_history_is_capped_at_today(self):
        from datetime import timedelta, datetime, time
        from django.utils import timezone
        from rest_framework.test import APIClient
        from accounts.models import User
        from fleet.models import Device
        from organizations.models import Subscription, SubscriptionDevice

        today = timezone.localdate()
        user = User.objects.create_user(
            username='personal_report_today_cap', password='test-password',
            role='personal_user', account_type='personal',
        )
        device = Device.objects.create(imei='860000000009931')
        contract = Subscription.objects.create(
            contract_number='PERSONAL-REPORT-TODAY-CAP', customer_type='personal',
            user=user, start_date=today-timedelta(days=5),
            end_date=today+timedelta(days=30), status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=contract, device=device,
            start_date=contract.start_date, end_date=contract.end_date,
        )
        client = APIClient()
        client.force_authenticate(user=user)

        metadata = client.get(
            '/api/devices/report-history/',
            {'device_id': device.pk, 'metadata': 'true'},
        )
        self.assertEqual(metadata.status_code, 200, metadata.data)
        self.assertEqual(
            timezone.localtime(datetime.fromisoformat(metadata.data['range_end'])).date(),
            today,
        )

        future_start = timezone.now() + timedelta(minutes=1)
        future_end = timezone.make_aware(
            datetime.combine(today + timedelta(days=1), time.max)
        )
        response = client.get('/api/devices/report-history/', {
            'device_id': device.pk,
            'from': future_start.isoformat(),
            'to': future_end.isoformat(),
        })
        self.assertEqual(response.status_code, 403)

    def test_company_report_history_is_capped_at_today(self):
        from datetime import timedelta, datetime, time
        from django.utils import timezone
        from rest_framework.test import APIClient
        from accounts.models import User
        from fleet.models import Device, DeviceCustomerAccessPeriod
        from organizations.models import Organization, Subscription, SubscriptionDevice

        today = timezone.localdate()
        organization = Organization.objects.create(
            name='Company Report Today Cap', code='COMPANY-REPORT-TODAY-CAP',
        )
        manager = User.objects.create_user(
            username='company_report_today_cap', password='test-password',
            role='main_user', account_type='organization', organization=organization,
        )
        device = Device.objects.create(imei='860000000009932', organization=organization)
        contract = Subscription.objects.create(
            contract_number='COMPANY-REPORT-TODAY-CAP', customer_type='organization',
            organization=organization, start_date=today-timedelta(days=5),
            end_date=today+timedelta(days=30), status='active',
        )
        SubscriptionDevice.objects.create(
            subscription=contract, device=device,
            start_date=contract.start_date, end_date=contract.end_date,
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device, organization=organization, subscription=contract,
            started_at=timezone.now()-timedelta(days=1),
        )
        client = APIClient()
        client.force_authenticate(user=manager)

        metadata = client.get(
            '/api/devices/report-history/',
            {'device_id': device.pk, 'metadata': 'true'},
        )
        self.assertEqual(metadata.status_code, 200, metadata.data)
        self.assertEqual(
            timezone.localtime(datetime.fromisoformat(metadata.data['range_end'])).date(),
            today,
        )

        future_start = timezone.now() + timedelta(minutes=1)
        future_end = timezone.make_aware(datetime.combine(today + timedelta(days=1), time.max))
        response = client.get('/api/devices/report-history/', {
            'device_id': device.pk,
            'from': future_start.isoformat(),
            'to': future_end.isoformat(),
        })
        self.assertEqual(response.status_code, 403)


class DeviceModelCountQueryEfficiencyTests(TestCase):
    def test_device_model_counts_are_annotated_without_per_model_queries(self):
        from types import SimpleNamespace
        from accounts.models import User
        from organizations.models import Organization
        from fleet.models import DeviceModel
        from fleet.serializers import DeviceModelSerializer
        from fleet.views import DeviceModelViewSet

        organization = Organization.objects.create(
            name='Model Count Query Organization',
            code='MODEL-COUNT-QUERY-ORG',
        )
        manager = User.objects.create_user(
            username='model_count_query_manager',
            password='test-password',
            role='main_user',
            account_type='organization',
            organization=organization,
        )
        for index in range(8):
            DeviceModel.objects.create(
                manufacturer='Query Efficiency',
                name=f'Model {index}',
                code=f'QUERY-EFFICIENCY-{index}',
                protocol='gt06',
                is_verified=True,
            )

        view = DeviceModelViewSet()
        view.request = SimpleNamespace(user=manager)
        queryset = view.get_queryset()

        with self.assertNumQueries(1):
            rows = DeviceModelSerializer(queryset, many=True).data

        self.assertEqual(len(rows), 8)
        self.assertTrue(all(row['devices_count'] == 0 for row in rows))


    def test_site_admin_sees_catalog_counts_across_all_tenants(self):
        from types import SimpleNamespace
        from accounts.models import User
        from fleet.models import Device, DeviceModel
        from fleet.serializers import DeviceModelSerializer
        from fleet.views import DeviceModelViewSet

        admin = User.objects.create_user(
            username='model_count_site_admin',
            password='test-password',
            role='site_admin',
            account_type='admin',
        )
        model = DeviceModel.objects.create(
            manufacturer='Admin Count',
            name='All Tenant Model',
            code='ADMIN-COUNT-ALL',
            protocol='gt06',
            is_verified=True,
        )
        Device.objects.create(
            imei='860000000009988',
            device_model=model,
        )
        Device.objects.create(
            imei='860000000009989',
            device_model=model,
        )

        view = DeviceModelViewSet()
        view.request = SimpleNamespace(user=admin)
        row = DeviceModelSerializer(view.get_queryset(), many=True).data[0]
        self.assertEqual(row['devices_count'], 2)


class BranchManagerReportHistoryDateUpperBoundTests(TestCase):
    def test_branch_manager_report_history_is_capped_at_today(self):
        from datetime import timedelta, datetime, time
        from django.utils import timezone
        from rest_framework.test import APIClient
        from accounts.models import User
        from fleet.models import Device, DeviceCustomerAccessPeriod
        from organizations.models import Branch, Organization, Subscription, SubscriptionDevice

        today = timezone.localdate()
        organization = Organization.objects.create(
            name='Branch Report Today Cap', code='BRANCH-REPORT-TODAY-CAP',
        )
        branch = Branch.objects.create(
            organization=organization,
            name='Branch Report Today Cap',
            code='BRANCH-REPORT-TODAY-CAP',
        )
        manager = User.objects.create_user(
            username='branch_report_today_cap', password='test-password',
            role='branch_manager', account_type='organization',
            organization=organization, branch=branch,
        )
        device = Device.objects.create(
            imei='860000000009933', organization=organization, branch=branch,
        )
        contract = Subscription.objects.create(
            contract_number='BRANCH-REPORT-TODAY-CAP', customer_type='organization',
            organization=organization, start_date=today-timedelta(days=5),
            end_date=today+timedelta(days=30), status='active',
        )
        link = SubscriptionDevice.objects.create(
            subscription=contract, device=device,
            start_date=contract.start_date, end_date=contract.end_date,
        )
        SubscriptionDevice.objects.filter(pk=link.pk).update(
            assigned_at=timezone.now()-timedelta(days=2),
        )
        DeviceCustomerAccessPeriod.objects.create(
            device=device, organization=organization, branch=branch,
            subscription=contract, started_at=timezone.now()-timedelta(days=1),
        )
        client = APIClient()
        client.force_authenticate(user=manager)

        metadata = client.get(
            '/api/devices/report-history/',
            {'device_id': device.pk, 'metadata': 'true'},
        )
        self.assertEqual(metadata.status_code, 200, metadata.data)
        self.assertEqual(
            timezone.localtime(datetime.fromisoformat(metadata.data['range_end'])).date(),
            today,
        )

        future_start = timezone.now() + timedelta(minutes=1)
        future_end = timezone.make_aware(
            datetime.combine(today + timedelta(days=1), time.max)
        )
        response = client.get('/api/devices/report-history/', {
            'device_id': device.pk,
            'from': future_start.isoformat(),
            'to': future_end.isoformat(),
        })
        self.assertEqual(response.status_code, 403)
