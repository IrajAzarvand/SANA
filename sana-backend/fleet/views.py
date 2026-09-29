from django.utils import timezone
from django.db.models import Exists, OuterRef
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated

from .models import VehicleType, Vehicle, DeviceModel, Device, Driver, DeviceLifecycleEvent, DeviceReplacementRelation
from .serializers import (
    VehicleTypeSerializer,
    VehicleSerializer,
    VehicleListSerializer,
    DeviceModelSerializer,
    DeviceSerializer,
    DeviceListSerializer,
    DriverSerializer,
    DeviceLifecycleEventSerializer,
    DeviceReplacementRelationSerializer,
)
from organizations.models import SubscriptionDevice
from accounts.permissions import IsSiteAdmin


class VehicleTypeViewSet(viewsets.ModelViewSet):
    queryset = VehicleType.objects.all()
    serializer_class = VehicleTypeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_site_admin:
            return VehicleType.objects.all()
        if user.organization_id:
            return VehicleType.objects.filter(organization_id=user.organization_id)
        return VehicleType.objects.none()


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.select_related('vehicle_type', 'organization', 'branch', 'owner_user').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['plate']
    ordering_fields = ['plate', 'created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return VehicleListSerializer
        return VehicleSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Vehicle.objects.select_related('vehicle_type', 'organization', 'branch', 'owner_user')

        if user.is_site_admin:
            pass
        elif user.is_main_user and user.organization:
            qs = qs.filter(organization=user.organization)
        elif user.is_branch_manager and user.branch:
            qs = qs.filter(branch=user.branch)
        elif user.is_personal_user:
            qs = qs.filter(owner_user=user)
        else:
            qs = qs.none()

        # فیلترها
        branch = self.request.query_params.get('branch')
        if branch:
            qs = qs.filter(branch_id=branch)

        organization = self.request.query_params.get('organization')
        if organization:
            qs = qs.filter(organization_id=organization)

        vehicle_type = self.request.query_params.get('vehicle_type')
        if vehicle_type:
            qs = qs.filter(vehicle_type_id=vehicle_type)

        return qs

    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            return [IsSiteAdmin()]
        return super().get_permissions()


class DeviceModelViewSet(viewsets.ModelViewSet):
    queryset = DeviceModel.objects.all()
    serializer_class = DeviceModelSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['manufacturer', 'name', 'code', 'protocol']
    ordering_fields = ['manufacturer', 'name', 'created_at']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsSiteAdmin()]
        return super().get_permissions()


class DeviceViewSet(viewsets.ModelViewSet):
    queryset = Device.objects.select_related('device_model', 'organization', 'branch', 'vehicle', 'owner_user').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['imei', 'sim_number']
    ordering_fields = ['created_at', 'imei']

    def get_serializer_class(self):
        if self.action == 'list':
            return DeviceListSerializer
        return DeviceSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Device.objects.select_related('device_model', 'organization', 'branch', 'vehicle', 'owner_user')

        if user.is_site_admin:
            pass
        elif user.is_main_user and user.organization:
            qs = qs.filter(organization=user.organization)
        elif user.is_branch_manager and user.branch:
            qs = qs.filter(branch=user.branch)
        elif user.is_personal_user:
            qs = qs.filter(owner_user=user)
        else:
            qs = qs.none()

        # ─── فیلترها ───

        # فیلتر شعبه
        branch = self.request.query_params.get('branch')
        if branch:
            qs = qs.filter(branch_id=branch)

        # فیلتر سازمان
        organization = self.request.query_params.get('organization')
        if organization:
            qs = qs.filter(organization_id=organization)

        # فیلتر وضعیت مدیریتی
        status = self.request.query_params.get('management_status')
        if status:
            qs = qs.filter(management_status=status)

        # فیلتر «فقط انبار» — دستگاه‌هایی که هیچ اتصال فعالی به قرارداد ندارن
        in_warehouse = self.request.query_params.get('in_warehouse')
        if in_warehouse == 'true':
            active_links = SubscriptionDevice.objects.filter(
                device=OuterRef('pk'),
                unassigned_at__isnull=True,
            )
            qs = qs.annotate(
                has_active_link=Exists(active_links)
            ).filter(
                management_status='warehouse',
                has_active_link=False,
            )

            
        # فیلتر «فقط فعال» — دستگاه‌هایی که یه اتصال فعال به قرارداد دارن
        active = self.request.query_params.get('active')
        if active == 'true':
            today = timezone.now().date()
            qs = qs.filter(
                subscription_links__unassigned_at__isnull=True,
                subscription_links__start_date__lte=today,
                subscription_links__end_date__gte=today,
                subscription_links__subscription__status='active',
            ).distinct()

        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsSiteAdmin()]
        return super().get_permissions()


class DriverViewSet(viewsets.ModelViewSet):
    queryset = Driver.objects.select_related('organization', 'branch').all()
    serializer_class = DriverSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name', 'mobile', 'personnel_code']
    ordering_fields = ['last_name', 'created_at']

    def get_queryset(self):
        user = self.request.user
        qs = Driver.objects.select_related('organization', 'branch')

        if user.is_site_admin:
            pass
        elif user.is_main_user and user.organization:
            qs = qs.filter(organization=user.organization)
        elif user.is_branch_manager and user.branch:
            qs = qs.filter(branch=user.branch)
        else:
            qs = qs.none()

        # فیلترها
        branch = self.request.query_params.get('branch')
        if branch:
            qs = qs.filter(branch_id=branch)

        return qs

class DeviceLifecycleEventViewSet(viewsets.ModelViewSet):
    """تاریخچه و ثبت رویدادهای چرخه عمر دستگاه."""
    queryset = DeviceLifecycleEvent.objects.select_related(
        'device', 'subscription', 'organization', 'user', 'vehicle', 'branch', 'performed_by'
    ).all()
    serializer_class = DeviceLifecycleEventSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['event_date', 'created_at']

    def get_queryset(self):
        user = self.request.user
        qs = self.queryset
        if user.is_site_admin:
            pass
        elif user.organization_id:
            qs = qs.filter(organization_id=user.organization_id)
        elif user.is_personal_user:
            qs = qs.filter(user=user)
        else:
            qs = qs.none()

        device = self.request.query_params.get('device')
        if device:
            qs = qs.filter(device_id=device)
        event_type = self.request.query_params.get('event_type')
        if event_type:
            qs = qs.filter(event_type=event_type)
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsSiteAdmin()]
        return super().get_permissions()


class DeviceReplacementRelationViewSet(viewsets.ModelViewSet):
    """رابطه‌های جایگزینی دستگاه‌ها؛ تغییر/ثبت فقط توسط ادمین سایت."""
    queryset = DeviceReplacementRelation.objects.select_related('source_device', 'replacement_device').all()
    serializer_class = DeviceReplacementRelationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['replacement_date', 'created_at']

    def get_queryset(self):
        user = self.request.user
        qs = self.queryset
        if user.is_site_admin:
            pass
        elif user.organization_id:
            qs = qs.filter(
                source_device__organization_id=user.organization_id
            ) | qs.filter(
                replacement_device__organization_id=user.organization_id
            )
        elif user.is_personal_user:
            qs = qs.filter(
                source_device__owner_user_id=user.id
            ) | qs.filter(
                replacement_device__owner_user_id=user.id
            )
        else:
            qs = qs.none()
        device = self.request.query_params.get('device')
        if device:
            qs = qs.filter(source_device_id=device) | qs.filter(replacement_device_id=device)
        return qs.distinct()

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsSiteAdmin()]
        return super().get_permissions()
