from rest_framework import serializers
from django.db.models import Q
from django.utils import timezone
from .customer_access import active_customer_access_periods, active_personal_contract_links, authorized_devices_for_user
from organizations.models import SubscriptionDevice
from .models import VehicleType, Vehicle, DeviceModel, Device, Driver, DriverVehicleAssignment, DeviceLifecycleEvent, DeviceReplacementRelation, DeviceOperation, DeviceCustomerAccessPeriod


def _device_data_active_for_request(device, request):
    """Evaluate service status against the exact contract granting this user access."""
    if not request or getattr(request.user, 'is_site_admin', False):
        return device.is_data_active

    user = request.user
    now = timezone.now()
    today = timezone.localdate(now)

    if getattr(user, 'is_personal_user', False):
        link = active_personal_contract_links(
            user_id=user.pk, now=now
        ).filter(device=device).first()
    elif getattr(user, 'is_main_user', False) and user.organization_id:
        access_periods = getattr(device, '_active_customer_access_periods', None)
        if access_periods is None:
            access_periods = active_customer_access_periods(
                organization_id=user.organization_id,
                now=now,
            ).filter(device=device).order_by('-started_at', '-id')
        access = access_periods[0] if access_periods else None
        prefetched_links = getattr(device, '_prefetched_subscription_links', None)
        if access and prefetched_links is not None:
            link = next((
                item for item in prefetched_links
                if item.subscription_id == access.subscription_id
                and item.unassigned_at is None
                and item.is_active
                and item.subscription
                and item.subscription.is_active
            ), None)
        else:
            link = (
                SubscriptionDevice.objects.filter(
                    device=device,
                    subscription_id=access.subscription_id,
                    assigned_at__lte=now,
                    unassigned_at__isnull=True,
                    start_date__lte=today,
                    end_date__gte=today,
                ).select_related('subscription').first()
                if access else None
            )
    elif getattr(user, 'is_branch_manager', False) and user.branch_id:
        access_periods = getattr(device, '_active_customer_access_periods', None)
        if access_periods is None:
            access_periods = active_customer_access_periods(
                organization_id=user.branch.organization_id,
                branch_id=user.branch_id,
                now=now,
            ).filter(device=device).order_by('-started_at', '-id')
        access = access_periods[0] if access_periods else None
        prefetched_links = getattr(device, '_prefetched_subscription_links', None)
        if access and prefetched_links is not None:
            link = next((
                item for item in prefetched_links
                if item.subscription_id == access.subscription_id
                and item.unassigned_at is None
                and item.is_active
                and item.subscription
                and item.subscription.is_active
            ), None)
        else:
            link = (
                SubscriptionDevice.objects.filter(
                    device=device,
                    subscription_id=access.subscription_id,
                    assigned_at__lte=now,
                    unassigned_at__isnull=True,
                    start_date__lte=today,
                    end_date__gte=today,
                ).select_related('subscription').first()
                if access else None
            )
    else:
        return False

    if not link or not link.is_active or not link.subscription or not link.subscription.is_active:
        return False
    return device.management_status not in {
        'faulty', 'in_repair', 'ready', 'lost', 'stolen',
        'disconnected', 'unusable', 'disposed',
    }


class VehicleTypeSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request and getattr(request.user, 'is_branch_manager', False):
            data['organization'] = None
        return data

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user if request else None
        if user and user.is_main_user:
            organization = attrs.get('organization', getattr(self.instance, 'organization', None))
            if organization and organization.pk != user.organization_id:
                raise serializers.ValidationError({'organization': 'نوع خودرو باید متعلق به سازمان خودتان باشد.'})
            attrs['organization'] = user.organization
        return attrs

    class Meta:
        model = VehicleType
        fields = ['id', 'name', 'organization', 'created_at']
        read_only_fields = ['id', 'created_at']


class VehicleSerializer(serializers.ModelSerializer):
    vehicle_type_name = serializers.CharField(source='vehicle_type.name', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    owner_name = serializers.CharField(source='owner_user.full_name', read_only=True)
    device_imei = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = [
            'id', 'plate',
            'vehicle_type', 'vehicle_type_name',
            'organization', 'organization_name',
            'owner_user', 'owner_name',
            'branch', 'branch_name',
            'device_imei',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'organization': {'required': False, 'allow_null': True},
            'owner_user': {'required': False, 'allow_null': True},
        }

    def get_device_imei(self, obj):
        request = self.context.get('request')
        if not request or not getattr(request.user, 'is_site_admin', False):
            if not request:
                return None
            authorized_ids = authorized_devices_for_user(
                request.user
            ).values_list('pk', flat=True)
            devices = obj.devices.filter(pk__in=authorized_ids)
        else:
            devices = obj.devices.all()

        device = devices.filter(management_status='active').order_by('-updated_at', '-id').first()
        return device.imei if device else None

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user if request else None
        if user and user.is_main_user:
            organization = attrs.get('organization', getattr(self.instance, 'organization', None))
            branch = attrs.get('branch', getattr(self.instance, 'branch', None))
            owner = attrs.get('owner_user', getattr(self.instance, 'owner_user', None))
            vehicle_type = attrs.get('vehicle_type', getattr(self.instance, 'vehicle_type', None))
            if organization and organization.pk != user.organization_id:
                raise serializers.ValidationError({'organization': 'خودرو باید متعلق به سازمان خودتان باشد.'})
            attrs['organization'] = user.organization
            if branch and branch.organization_id != user.organization_id:
                raise serializers.ValidationError({'branch': 'شعبه انتخاب‌شده متعلق به سازمان شما نیست.'})
            if owner and owner.organization_id != user.organization_id:
                raise serializers.ValidationError({'owner_user': 'مالک انتخاب‌شده متعلق به سازمان شما نیست.'})
            if vehicle_type and vehicle_type.organization_id not in (None, user.organization_id):
                raise serializers.ValidationError({'vehicle_type': 'نوع خودرو متعلق به سازمان دیگری است.'})
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        if request:
            user = request.user
            # اگه سازمانی بود و organization انتخاب نشده
            if user.account_type == 'organization' and user.organization_id:
                validated_data.setdefault('organization_id', user.organization_id)
            # اگه شخصی بود، owner_user = خود کاربر
            elif user.account_type == 'personal':
                validated_data['owner_user'] = user

        return super().create(validated_data)

class VehicleListSerializer(serializers.ModelSerializer):
    vehicle_type_name = serializers.CharField(source='vehicle_type.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    device_status = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = [
            'id', 'plate',
            'vehicle_type_name', 'branch_name',
            'device_status',
            'created_at',
        ]

    def get_device_status(self, obj):
        request = self.context.get('request')
        if not request:
            return 'none'
        devices = obj.devices.filter(
            pk__in=authorized_devices_for_user(request.user).values_list('pk', flat=True)
        )
        device = devices.order_by('-updated_at', '-id').first()
        if not device:
            return 'none'
        return 'active' if _device_data_active_for_request(device, request) else 'offline'


class DeviceModelSerializer(serializers.ModelSerializer):
    devices_count = serializers.IntegerField(source='devices.count', read_only=True)

    class Meta:
        model = DeviceModel
        fields = ['id', 'manufacturer', 'name', 'code', 'protocol', 'port', 'traccar_version', 'source_url', 'is_verified', 'devices_count', 'created_at']
        read_only_fields = ['id', 'created_at']

class DeviceSerializer(serializers.ModelSerializer):
    def validate_device_model(self, value):
        if value and not value.is_verified:
            raise serializers.ValidationError(
                'مدل انتخاب‌شده در فهرست رسمی فعلی Traccar فعال نیست.'
            )
        return value


    current_holder_organization_name = serializers.CharField(source='current_holder_organization.name', read_only=True)
    current_holder_user_name = serializers.CharField(source='current_holder_user.full_name', read_only=True)
    device_model_name = serializers.CharField(source='device_model.name', read_only=True, allow_null=True)
    device_model_manufacturer = serializers.CharField(source='device_model.manufacturer', read_only=True, allow_null=True)
    device_model_port = serializers.IntegerField(source='device_model.port', read_only=True, allow_null=True)
    device_model_catalog_protocol = serializers.CharField(source='device_model.protocol', read_only=True, allow_null=True)
    protocol = serializers.CharField(read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    owner_name = serializers.CharField(source='owner_user.full_name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate', read_only=True)
    management_status = serializers.SerializerMethodField()
    data_active = serializers.SerializerMethodField()

    def get_management_status(self, obj):
        request = self.context.get('request')
        if request and not getattr(request.user, 'is_site_admin', False):
            return None
        if obj.is_in_warehouse:
            return 'warehouse'
        return obj.management_status

    def get_data_active(self, obj):
        return _device_data_active_for_request(obj, self.context.get('request'))

    class Meta:
        model = Device
        fields = [
            'id', 'imei',
            'device_model', 'device_model_name', 'device_model_manufacturer', 'device_model_port', 'device_model_catalog_protocol', 'protocol',
            'organization', 'organization_name',
            'owner_user', 'owner_name',
            'branch', 'branch_name',
            'current_holder_organization', 'current_holder_organization_name',
            'current_holder_user', 'current_holder_user_name',
            'vehicle', 'vehicle_plate',
            'sim_number',
            'management_status',
            'data_active',
            'installed_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'protocol']
        extra_kwargs = {
            'organization': {'required': False, 'allow_null': True},
            'owner_user': {'required': False, 'allow_null': True},
            'vehicle': {'required': False, 'allow_null': True},
        }

    def validate(self, attrs):
        protected_relationships = (
            'organization',
            'owner_user',
            'current_holder_organization',
            'current_holder_user',
            'branch',
            'vehicle',
        )
        if self.instance is not None:
            for field_name in protected_relationships:
                if field_name not in attrs:
                    continue
                current_id = getattr(self.instance, f'{field_name}_id')
                new_id = getattr(attrs[field_name], 'pk', None)
                if current_id != new_id:
                    raise serializers.ValidationError({
                        field_name: 'تغییر مالکیت، تحویل‌گیرنده، شعبه یا خودرو فقط از عملیات رسمی چرخه عمر دستگاه مجاز است.'
                    })
        else:
            for field_name in (
                'current_holder_organization',
                'current_holder_user',
                'branch',
                'vehicle',
            ):
                if attrs.get(field_name) is not None:
                    raise serializers.ValidationError({
                        field_name: 'تخصیص مشتری، شعبه و خودرو فقط پس از اتصال رسمی دستگاه به قرارداد مجاز است.'
                    })

        for field_name in ('owner_user', 'current_holder_user'):
            if field_name in attrs and attrs[field_name] is not None:
                if not attrs[field_name].is_personal_user:
                    raise serializers.ValidationError({
                        field_name: 'هویت شخصی دستگاه باید حساب دارای نقش مشتری شخصی باشد.'
                    })
                if field_name == 'owner_user' and not attrs[field_name].is_active:
                    raise serializers.ValidationError({
                        field_name: 'مالک شخصی دستگاه باید حساب فعال داشته باشد.'
                    })

        request = self.context.get('request')
        user = request.user if request else None
        if user and user.is_main_user:
            organization = attrs.get('organization', getattr(self.instance, 'organization', None))
            branch = attrs.get('branch', getattr(self.instance, 'branch', None))
            vehicle = attrs.get('vehicle', getattr(self.instance, 'vehicle', None))
            if organization and organization.pk != user.organization_id:
                raise serializers.ValidationError({'organization': 'دستگاه باید متعلق به سازمان خودتان باشد.'})
            attrs['organization'] = user.organization
            if branch and branch.organization_id != user.organization_id:
                raise serializers.ValidationError({'branch': 'شعبه انتخاب‌شده متعلق به سازمان شما نیست.'})
            if vehicle and vehicle.organization_id != user.organization_id:
                raise serializers.ValidationError({'vehicle': 'خودرو انتخاب‌شده متعلق به سازمان شما نیست.'})
            owner = attrs.get('owner_user', getattr(self.instance, 'owner_user', None))
            if owner and owner.organization_id != user.organization_id:
                raise serializers.ValidationError({'owner_user': 'مالک دستگاه متعلق به سازمان شما نیست.'})
            holder_org = attrs.get('current_holder_organization', getattr(self.instance, 'current_holder_organization', None))
            if holder_org and holder_org.pk != user.organization_id:
                raise serializers.ValidationError({'current_holder_organization': 'دارنده دستگاه باید سازمان خودتان باشد.'})
            holder_user = attrs.get('current_holder_user', getattr(self.instance, 'current_holder_user', None))
            if holder_user and holder_user.organization_id != user.organization_id:
                raise serializers.ValidationError({'current_holder_user': 'دارنده دستگاه متعلق به سازمان شما نیست.'})
            if vehicle and branch and vehicle.branch_id and vehicle.branch_id != branch.pk:
                raise serializers.ValidationError({'vehicle': 'خودرو و دستگاه باید در یک شعبه باشند.'})
        if self.instance is not None and 'organization' in attrs:
            if getattr(attrs['organization'], 'pk', None) != self.instance.organization_id:
                raise serializers.ValidationError({
                    'organization': 'تغییر مالک قانونی فقط از عملیات رسمی انتقال مالکیت مجاز است.'
                })
        return attrs

    def create(self, validated_data):
        from django.db import transaction
        from .device_operations import _open_ownership
        from .lifecycle import record_device_lifecycle_event

        with transaction.atomic():
            request = self.context.get('request')
            if request:
                user = request.user
                if user.account_type == 'organization' and user.organization_id:
                    validated_data.setdefault('organization_id', user.organization_id)
                elif user.account_type == 'personal':
                    validated_data['owner_user'] = user

            instance = super().create(validated_data)
            if instance.organization_id or instance.owner_user_id:
                _open_ownership(
                    instance,
                    organization=instance.organization,
                    user=instance.owner_user,
                    reason='device_received',
                )
            record_device_lifecycle_event(
                device=instance,
                event_type='received',
                performed_by=request.user if request else None,
                description='دستگاه به موجودی سانا اضافه شد.',
            )
            return instance

class BranchManagerDeviceSerializer(serializers.ModelSerializer):
    device_model_name = serializers.CharField(source='device_model.name', read_only=True, allow_null=True)
    device_model_manufacturer = serializers.CharField(source='device_model.manufacturer', read_only=True, allow_null=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate', read_only=True)
    data_active = serializers.SerializerMethodField()
    last_data_received_at = serializers.DateTimeField(read_only=True, allow_null=True)

    def get_data_active(self, obj):
        return _device_data_active_for_request(obj, self.context.get('request'))

    class Meta:
        model = Device
        fields = [
            'id', 'imei', 'device_model_name', 'device_model_manufacturer',
            'protocol', 'sim_number', 'branch_name', 'vehicle_plate',
            'data_active', 'last_data_received_at', 'installed_at', 'created_at',
        ]


class DeviceListSerializer(serializers.ModelSerializer):
    management_status = serializers.SerializerMethodField()
    data_active = serializers.SerializerMethodField()
    data_inactive_reason = serializers.SerializerMethodField()
    is_in_warehouse = serializers.SerializerMethodField()

    def _active_subscription_link(self, obj):
        """Return the exact currently valid contract link for this request."""
        if hasattr(obj, '_list_active_subscription_link'):
            return obj._list_active_subscription_link

        request = self.context.get('request')
        user = request.user if request else None
        now = timezone.now()
        today = timezone.localdate(now)
        links = getattr(obj, '_prefetched_subscription_links', None)

        def is_current(link):
            subscription = getattr(link, 'subscription', None)
            return bool(
                link.unassigned_at is None
                and link.assigned_at <= now
                and link.start_date <= today <= link.end_date
                and subscription
                and subscription.status == 'active'
                and subscription.start_date <= today <= subscription.end_date
                and subscription.computed_status == 'active'
            )

        if user and getattr(user, 'is_site_admin', False):
            if links is None:
                latest_started = obj.subscription_links.filter(
                    assigned_at__lte=now
                ).select_related('subscription').order_by('-assigned_at', '-id').first()
            else:
                started_links = [
                    item for item in links if item.assigned_at <= now
                ]
                latest_started = max(
                    started_links,
                    key=lambda item: (item.assigned_at, item.pk),
                    default=None,
                )
            link = (
                latest_started
                if latest_started and latest_started.unassigned_at is None
                else None
            )
        elif user and getattr(user, 'is_personal_user', False):
            def belongs_to_user(link):
                subscription = getattr(link, 'subscription', None)
                return bool(
                    subscription
                    and subscription.user_id == user.pk
                    and subscription.customer_type == 'personal'
                    and is_current(link)
                )

            if links is None:
                link = active_personal_contract_links(
                    user_id=user.pk, now=now
                ).filter(device=obj).first()
            else:
                link = next((item for item in links if belongs_to_user(item)), None)
        elif user and (
            getattr(user, 'is_main_user', False)
            or getattr(user, 'is_branch_manager', False)
        ):
            access_periods = getattr(obj, '_active_customer_access_periods', None)
            if access_periods is None:
                if getattr(user, 'is_main_user', False) and user.organization_id:
                    periods = active_customer_access_periods(
                        organization_id=user.organization_id, now=now
                    )
                elif getattr(user, 'is_branch_manager', False) and user.branch_id:
                    periods = active_customer_access_periods(
                        organization_id=user.branch.organization_id,
                        branch_id=user.branch_id,
                        now=now,
                    )
                else:
                    periods = DeviceCustomerAccessPeriod.objects.none()
                access_periods = periods.filter(device=obj).order_by('-started_at', '-id')

            access_period = access_periods[0] if access_periods else None
            if access_period is None:
                link = None
            elif links is None:
                link = SubscriptionDevice.objects.filter(
                    device=obj,
                    subscription_id=access_period.subscription_id,
                    subscription__status='active',
                    subscription__start_date__lte=today,
                    subscription__end_date__gte=today,
                    assigned_at__lte=now,
                    unassigned_at__isnull=True,
                    start_date__lte=today,
                    end_date__gte=today,
                ).select_related('subscription').order_by('-assigned_at', '-id').first()
            else:
                link = next((
                    item for item in links
                    if item.subscription_id == access_period.subscription_id
                    and is_current(item)
                ), None)
        else:
            if links is None:
                latest_started = obj.subscription_links.filter(
                    assigned_at__lte=now
                ).select_related('subscription').order_by('-assigned_at', '-id').first()
            else:
                started_links = [
                    item for item in links if item.assigned_at <= now
                ]
                latest_started = max(
                    started_links,
                    key=lambda item: (item.assigned_at, item.pk),
                    default=None,
                )
            link = (
                latest_started
                if latest_started and latest_started.unassigned_at is None
                else None
            )

        obj._list_active_subscription_link = link
        return link

    def _is_in_warehouse(self, obj):
        return (
            obj.management_status == 'warehouse'
            and self._active_subscription_link(obj) is None
        )

    def get_is_in_warehouse(self, obj):
        request = self.context.get('request')
        if request and not getattr(request.user, 'is_site_admin', False):
            return None
        return self._is_in_warehouse(obj)

    def get_data_active(self, obj):
        link = self._active_subscription_link(obj)
        if not link or not link.is_active:
            return False

        # A device link can remain unassigned_at=None after a contract is
        # suspended, cancelled, not-yet-started, or expired. Contract dates
        # and its computed status must both authorize data service.
        subscription = getattr(link, 'subscription', None)
        if (
            not subscription
            or subscription.status != 'active'
            or subscription.computed_status != 'active'
        ):
            return False

        if obj.management_status in {
            'faulty', 'in_repair', 'ready', 'lost', 'stolen',
            'disconnected', 'unusable', 'disposed',
        }:
            return False
        return True

    def get_data_inactive_reason(self, obj):
        """Return internal diagnostics to admins and a simple service message to customers."""
        request = self.context.get('request')
        is_admin = not request or getattr(request.user, 'is_site_admin', False)
        if not is_admin and not self.get_data_active(obj):
            return 'سرویس دستگاه در حال حاضر فعال نیست'
        link = self._active_subscription_link(obj)
        if not link:
            return 'دستگاه به هیچ قراردادی متصل نیست'

        today = timezone.localdate()
        if not link.is_active:
            if link.start_date > today:
                return 'تاریخ شروع تخصیص دستگاه هنوز نرسیده'
            if link.end_date < today:
                return 'مهلت تخصیص دستگاه به پایان رسیده'
            return 'اتصال دستگاه به قرارداد فعال نیست'

        subscription = getattr(link, 'subscription', None)
        if not subscription:
            return 'قرارداد مرتبط پیدا نشد'

        contract_status_reasons = {
            'suspended': 'قرارداد تعلیق شده است',
            'cancelled': 'قرارداد لغو شده است',
            'expired': 'قرارداد منقضی شده است',
            'pending': 'تاریخ شروع قرارداد هنوز نرسیده',
        }
        contract_status = (
            subscription.status
            if subscription.status in {'suspended', 'cancelled', 'expired'}
            else subscription.computed_status
        )
        if contract_status != 'active':
            return contract_status_reasons.get(
                contract_status,
                'وضعیت قرارداد اجازه ارائه سرویس نمی‌دهد',
            )

        management_status_reasons = {
            'faulty': 'دستگاه خراب است',
            'in_repair': 'دستگاه در حال تعمیر است',
            'ready': 'دستگاه آماده تعیین تکلیف است',
            'lost': 'دستگاه گمشده ثبت شده است',
            'stolen': 'دستگاه سرقت‌شده ثبت شده است',
            'disconnected': 'سرویس دستگاه قطع شده است',
            'unusable': 'دستگاه غیرقابل استفاده است',
            'disposed': 'دستگاه امحاء شده است',
        }
        return management_status_reasons.get(obj.management_status)

    def get_management_status(self, obj):
        """Management lifecycle is an admin-only field."""
        request = self.context.get('request')
        if request and not getattr(request.user, 'is_site_admin', False):
            return None
        if self._is_in_warehouse(obj):
            return 'warehouse'
        return obj.management_status

    device_model_name = serializers.CharField(source='device_model.name', read_only=True, allow_null=True)
    device_model_manufacturer = serializers.CharField(source='device_model.manufacturer', read_only=True, allow_null=True)
    traccar_model = serializers.SerializerMethodField()
    traccar_protocol = serializers.SerializerMethodField()
    protocol = serializers.CharField(read_only=True)

    def get_traccar_model(self, obj):
        """Return the raw model reported by Traccar for this list response only."""
        return getattr(obj, 'traccar_model', None)

    def get_traccar_protocol(self, obj):
        """Return the live decoder protocol from Traccar's current position."""
        return getattr(obj, 'traccar_protocol', None)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    owner_name = serializers.CharField(source='owner_user.full_name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    current_holder_organization_name = serializers.CharField(source='current_holder_organization.name', read_only=True)
    current_holder_user_name = serializers.CharField(source='current_holder_user.full_name', read_only=True)
    customer_name = serializers.SerializerMethodField()

    # اطلاعات قرارداد مرتبط با دستگاه (فعال یا تاریخی)
    subscription_id = serializers.SerializerMethodField()
    subscription_number = serializers.SerializerMethodField()
    subscription_end_date = serializers.SerializerMethodField()
    subscription_device_type = serializers.SerializerMethodField()
    subscription_device_type_display = serializers.SerializerMethodField()
    replacement_device_id = serializers.SerializerMethodField()
    replacement_device_imei = serializers.SerializerMethodField()
    replacement_relation_direction = serializers.SerializerMethodField()

    # وضعیت دریافت داده از GPS
    last_data_received_at = serializers.DateTimeField(read_only=True, allow_null=True)

    class Meta:
        model = Device
        fields = [
            'id', 'imei',
            'device_model_name', 'device_model_manufacturer', 'traccar_model', 'protocol', 'traccar_protocol',
            'sim_number',
            'organization', 'organization_name',
            'owner_user', 'owner_name',
            'branch', 'branch_name',
            'current_holder_organization_name', 'current_holder_user_name',
            'customer_name',
            'vehicle_plate',
            'subscription_id', 'subscription_number', 'subscription_end_date',
            'subscription_device_type', 'subscription_device_type_display',
            'replacement_device_id', 'replacement_device_imei', 'replacement_relation_direction',
            'management_status',
            'data_active',
            'data_inactive_reason',
            'last_data_received_at',
            'is_in_warehouse',
            'created_at',
        ]

    def get_customer_name(self, obj):
        # The current contract is the strongest source for the customer shown
        # in this table. Ownership/holder fields remain fallbacks for devices
        # that are not currently linked to a contract.
        link = self._display_subscription_link(obj)
        if link and link.subscription:
            contract_customer = link.subscription.get_customer_name()
            if contract_customer and contract_customer != '—':
                return contract_customer

        if obj.current_holder_organization:
            return obj.current_holder_organization.name
        if obj.current_holder_user:
            return obj.current_holder_user.full_name or obj.current_holder_user.username
        if obj.organization:
            return obj.organization.name
        if obj.owner_user:
            return obj.owner_user.full_name or obj.owner_user.username
        return None

    def _display_subscription_link(self, obj):
        """Return only a currently valid contract assignment for the device list.

        Historical links and legacy replacement operations belong in history
        views; they must never be presented as the device's current contract.
        """
        if hasattr(obj, '_display_subscription_link_cache'):
            return obj._display_subscription_link_cache

        link = self._active_subscription_link(obj)
        subscription = getattr(link, 'subscription', None) if link else None

        # The assignment period and the contract itself must both be current.
        # A non-null unassigned_at is already excluded by
        # _active_subscription_link(); is_active also checks the device dates.
        if (
            link
            and getattr(link, 'is_active', False)
            and subscription
            and subscription.status == 'active'
            and subscription.computed_status == 'active'
        ):
            result = link
        else:
            result = None

        obj._display_subscription_link_cache = result
        return result

    def get_subscription_id(self, obj):
        link = self._display_subscription_link(obj)
        return link.subscription.id if link else None

    def get_subscription_number(self, obj):
        link = self._display_subscription_link(obj)
        return link.subscription.contract_number if link else None

    def get_subscription_end_date(self, obj):
        link = self._display_subscription_link(obj)
        if not link:
            return None
        return getattr(link, 'end_date', None) or getattr(link.subscription, 'end_date', None)

    def _current_replacement_operation(self, obj):
        link = self._active_subscription_link(obj)
        if not link:
            return None

        # B is the replacement device in the return-for-repair operation.
        # Match the operation to the currently active contract so an old
        # replacement history cannot affect the current device role.
        operations = getattr(
            obj, '_prefetched_replacement_target_operations', None
        )
        if operations is not None:
            return next(
                (
                    operation for operation in operations
                    if operation.operation_type == 'return_for_repair'
                    and operation.subscription_id == link.subscription_id
                ),
                None,
            )

        return obj.replacement_operations.filter(
            operation_type='return_for_repair',
            subscription=link.subscription,
        ).order_by('-performed_at', '-id').first()

    def get_subscription_device_type(self, obj):
        link = self._display_subscription_link(obj)
        if not link:
            return 'free'

        replacement_operation = self._current_replacement_operation(obj)
        if replacement_operation and replacement_operation.replacement_type:
            return replacement_operation.replacement_type

        # Fallback for existing records created before DeviceOperation was
        # linked consistently: the replacement relation still contains the
        # authoritative replacement type.
        replacement_relations = getattr(
            obj, '_replacement_relations_as_replacement', None
        )
        if replacement_relations is None:
            relation = obj.replacement_relations_as_replacement.order_by(
                '-replacement_date', '-id'
            ).first()
        else:
            relation = replacement_relations[0] if replacement_relations else None
        if relation:
            return relation.replacement_type

        # The source device remains in the contract after replacement.
        # While it is out of operation, show its relationship as «replaced»
        # instead of incorrectly presenting it as the current primary device.
        source_relations = getattr(
            obj, '_replacement_relations_as_source', None
        )
        if source_relations is None:
            source_relation = obj.replacement_relations_as_source.order_by(
                '-replacement_date', '-id'
            ).first()
        else:
            source_relation = source_relations[0] if source_relations else None
        if source_relation and obj.management_status in {
            'faulty', 'in_repair', 'lost', 'stolen', 'ready'
        }:
            return 'replaced'

        return 'primary'

    def get_management_status(self, obj):
        request = self.context.get('request')
        if request and not getattr(request.user, 'is_site_admin', False):
            return None
        if self._is_in_warehouse(obj):
            return 'warehouse'

        replacement_operation = self._current_replacement_operation(obj)
        if replacement_operation and replacement_operation.replacement_type:
            if replacement_operation.replacement_type == 'temporary_repair':
                return 'installed'
            if replacement_operation.replacement_type == 'permanent_replacement':
                return 'installed'

        return obj.management_status

    def get_subscription_device_type_display(self, obj):
        value = self.get_subscription_device_type(obj)
        return {
            'primary': 'اصلی',
            'temporary_repair': 'جایگزین موقت',
            'permanent_replacement': 'جایگزین دائم',
            'replacement': 'جایگزین دائم',
            'replaced': 'اصلی',
            'free': 'آزاد',
        }.get(value)

    def _latest_replacement_relation(self, obj):
        relations = []
        for relation in getattr(obj, '_replacement_relations_as_source', []):
            relations.append(('source', relation))
        for relation in getattr(obj, '_replacement_relations_as_replacement', []):
            relations.append(('replacement', relation))
        if not relations:
            return None, None
        direction, relation = max(
            relations,
            key=lambda item: (item[1].replacement_date, item[1].id),
        )
        return direction, relation

    def get_replacement_device_id(self, obj):
        direction, relation = self._latest_replacement_relation(obj)
        if not relation:
            return None
        return relation.replacement_device_id if direction == 'source' else relation.source_device_id

    def get_replacement_device_imei(self, obj):
        direction, relation = self._latest_replacement_relation(obj)
        if not relation:
            return None
        return relation.replacement_device.imei if direction == 'source' else relation.source_device.imei

    def get_replacement_relation_direction(self, obj):
        direction, relation = self._latest_replacement_relation(obj)
        if not relation:
            return None
        return 'replaced_by' if direction == 'source' else 'replacement_for'

class DriverSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request and getattr(request.user, 'is_branch_manager', False):
            data['organization'] = None
            data['organization_name'] = None
        return data
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Driver
        fields = [
            'id', 'first_name', 'last_name', 'full_name',
            'national_id', 'mobile',
            'personnel_code', 'position',
            'license_number', 'license_type', 'license_expiry',
            'organization', 'organization_name',
            'branch', 'branch_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']
        extra_kwargs = {
            'organization': {'required': False, 'allow_null': True},
        }

    def get_full_name(self, obj):
        return f'{obj.first_name} {obj.last_name}'

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user if request else None
        if not user or user.is_site_admin:
            return attrs

        if not (user.is_main_user or user.is_branch_manager):
            raise serializers.ValidationError('اجازه مدیریت رانندگان را ندارید.')
        if not user.organization_id:
            raise serializers.ValidationError('حساب شما به سازمان معتبری متصل نیست.')

        branch = attrs.get('branch', getattr(self.instance, 'branch', None))
        if user.is_branch_manager:
            if not user.branch_id:
                raise serializers.ValidationError('حساب مدیر شعبه به شعبه معتبری متصل نیست.')
            if branch and branch.pk != user.branch_id:
                raise serializers.ValidationError({
                    'branch': 'شما فقط می‌توانید رانندگان شعبه خود را مدیریت کنید.'
                })
            # A branch manager cannot move a driver out of, or into, another branch.
            attrs['branch'] = user.branch
        elif branch and branch.organization_id != user.organization_id:
            raise serializers.ValidationError({
                'branch': 'شعبه انتخاب‌شده متعلق به سازمان شما نیست.'
            })

        return attrs

    def create(self, validated_data):
        # organization رو از کاربر جاری پر کن
        request = self.context.get('request')
        if request and request.user.organization_id:
            validated_data['organization_id'] = request.user.organization_id
        return super().create(validated_data)

class DriverVehicleAssignmentSerializer(serializers.ModelSerializer):
    driver_name = serializers.SerializerMethodField()
    vehicle_plate = serializers.CharField(source='vehicle.plate', read_only=True)
    driver_branch_name = serializers.CharField(source='driver.branch.name', read_only=True)
    vehicle_branch_name = serializers.CharField(source='vehicle.branch.name', read_only=True)

    class Meta:
        model = DriverVehicleAssignment
        fields = [
            'id', 'driver', 'driver_name',
            'vehicle', 'vehicle_plate',
            'driver_branch_name', 'vehicle_branch_name',
            'started_at', 'ended_at', 'created_at',
        ]
        read_only_fields = [
            'id', 'driver_name', 'vehicle_plate',
            'driver_branch_name', 'vehicle_branch_name', 'created_at',
        ]

    def get_driver_name(self, obj):
        return str(obj.driver)

    def validate(self, attrs):
        driver = attrs.get('driver', getattr(self.instance, 'driver', None))
        vehicle = attrs.get('vehicle', getattr(self.instance, 'vehicle', None))
        started_at = attrs.get('started_at', getattr(self.instance, 'started_at', None))
        ended_at = attrs.get('ended_at', getattr(self.instance, 'ended_at', None))

        if not driver or not vehicle:
            raise serializers.ValidationError('راننده و خودرو الزامی هستند.')

        if driver.organization_id != vehicle.organization_id:
            raise serializers.ValidationError({'vehicle': 'راننده و خودرو باید متعلق به یک سازمان باشند.'})

        request = self.context.get('request')
        user = request.user if request else None
        if user and not user.is_site_admin:
            if not user.organization_id or driver.organization_id != user.organization_id:
                raise serializers.ValidationError({'driver': 'این راننده متعلق به سازمان شما نیست.'})
            if user.is_branch_manager and driver.branch_id != user.branch_id:
                raise serializers.ValidationError({'driver': 'شما فقط می‌توانید رانندگان شعبه خود را مدیریت کنید.'})
            if user.is_branch_manager and vehicle.branch_id and vehicle.branch_id != user.branch_id:
                raise serializers.ValidationError({'vehicle': 'شما فقط می‌توانید خودروهای شعبه خود را مدیریت کنید.'})

        if driver.branch_id and vehicle.branch_id and driver.branch_id != vehicle.branch_id:
            raise serializers.ValidationError({'vehicle': 'شعبه راننده و خودرو باید یکسان باشد.'})

        if ended_at and ended_at <= started_at:
            raise serializers.ValidationError({'ended_at': 'پایان تخصیص باید بعد از شروع تخصیص باشد.'})

        overlap = DriverVehicleAssignment.objects.filter(vehicle=vehicle)
        if ended_at:
            overlap = overlap.filter(
                started_at__lt=ended_at,
            ).filter(
                Q(ended_at__isnull=True) | Q(ended_at__gt=started_at)
            )
        else:
            overlap = overlap.filter(
                Q(ended_at__isnull=True) | Q(ended_at__gt=started_at)
            )
        if self.instance:
            overlap = overlap.exclude(pk=self.instance.pk)
        if overlap.exists():
            raise serializers.ValidationError({'vehicle': 'این بازه زمانی با تخصیص دیگری به این خودرو تداخل دارد.'})

        return attrs


class DeviceLifecycleEventSerializer(serializers.ModelSerializer):
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    device_imei = serializers.CharField(source='device.imei', read_only=True)
    subscription_number = serializers.CharField(source='subscription.contract_number', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DeviceLifecycleEvent
        fields = [
            'id', 'device', 'device_operation', 'device_imei', 'event_type', 'event_type_display',
            'event_date', 'subscription', 'subscription_number',
            'organization', 'organization_name', 'user', 'user_name',
            'vehicle', 'vehicle_plate', 'branch', 'branch_name',
            'reason', 'reason_display', 'description',
            'previous_status', 'new_status', 'performed_by', 'performed_by_name',
            'created_at',
        ]
        read_only_fields = [
            'id', 'device_operation', 'device_imei', 'event_type_display', 'reason_display',
            'subscription_number', 'organization_name', 'user_name',
            'vehicle_plate', 'branch_name', 'previous_status', 'new_status',
            'performed_by', 'performed_by_name', 'created_at',
        ]

    def get_performed_by_name(self, obj):
        if not obj.performed_by:
            return None
        return obj.performed_by.full_name or obj.performed_by.username

    def validate(self, data):
        device = data.get('device')
        event_type = data.get('event_type')
        subscription = data.get('subscription')
        if event_type == 'assigned_to_contract' and not subscription:
            raise serializers.ValidationError({'subscription': 'برای اتصال به قرارداد، انتخاب قرارداد الزامی است'})
        if event_type == 'returned' and device and device.subscription_links.filter(unassigned_at__isnull=True).exists():
            raise serializers.ValidationError({'device': 'دستگاه تا زمانی که قرارداد فعال دارد نمی‌تواند به سانا برگردانده شود'})
        if subscription and device:
            if not subscription.subscription_devices.filter(device=device).exists():
                raise serializers.ValidationError({'subscription': 'این دستگاه در سابقه این قرارداد وجود ندارد'})
        return data

    def create(self, validated_data):
        from .lifecycle import record_device_lifecycle_event
        device = validated_data.pop('device')
        event_type = validated_data.pop('event_type')
        request = self.context.get('request')
        performed_by = request.user if request else None
        subscription = validated_data.get('subscription')
        if subscription is not None:
            # Lifecycle events attached to a contract must identify the
            # contract customer, not the device's legal owner.
            validated_data['organization'] = subscription.organization
            validated_data['user'] = subscription.user
        return record_device_lifecycle_event(
            device=device,
            event_type=event_type,
            performed_by=performed_by,
            **validated_data,
        )


class DeviceReplacementRelationSerializer(serializers.ModelSerializer):
    replacement_type_display = serializers.CharField(source='get_replacement_type_display', read_only=True)
    source_device_imei = serializers.CharField(source='source_device.imei', read_only=True)
    replacement_device_imei = serializers.CharField(source='replacement_device.imei', read_only=True)

    class Meta:
        model = DeviceReplacementRelation
        fields = [
            'id', 'source_device', 'source_device_imei',
            'replacement_device', 'replacement_device_imei',
            'replacement_type', 'replacement_type_display',
            'replacement_date', 'description', 'created_at',
        ]
        read_only_fields = [
            'id', 'source_device_imei', 'replacement_device_imei',
            'replacement_type_display', 'created_at',
        ]

    def validate(self, data):
        if data.get('source_device') == data.get('replacement_device'):
            raise serializers.ValidationError({'replacement_device': 'دستگاه جایگزین نمی‌تواند همان دستگاه قبلی باشد.'})
        return data


class DeviceOperationSerializer(serializers.ModelSerializer):
    operation_type_display = serializers.CharField(source='get_operation_type_display', read_only=True)
    device_imei = serializers.CharField(source='device.imei', read_only=True)
    replacement_device_imei = serializers.CharField(source='replacement_device.imei', read_only=True)
    subscription_number = serializers.CharField(source='subscription.contract_number', read_only=True)
    target_subscription_number = serializers.CharField(source='target_subscription.contract_number', read_only=True)
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DeviceOperation
        fields = [
            'id', 'operation_type', 'operation_type_display',
            'device', 'device_imei',
            'replacement_device', 'replacement_device_imei',
            'subscription', 'subscription_number',
            'target_subscription', 'target_subscription_number',
            'target_organization', 'target_user', 'target_branch', 'target_vehicle',
            'replacement_type', 'reason', 'description',
            'old_status', 'new_status', 'performed_at',
            'performed_by', 'performed_by_name',
        ]
        read_only_fields = [
            'id', 'operation_type_display', 'device_imei', 'replacement_device_imei',
            'subscription_number', 'target_subscription_number',
            'old_status', 'new_status', 'performed_at', 'performed_by', 'performed_by_name',
        ]

    def get_performed_by_name(self, obj):
        if not obj.performed_by:
            return None
        return obj.performed_by.full_name or obj.performed_by.username

    def validate(self, data):
        if data.get('replacement_device') and data['replacement_device'].pk == data['device'].pk:
            raise serializers.ValidationError({'replacement_device': 'دستگاه جایگزین نمی‌تواند همان دستگاه قبلی باشد.'})
        return data

    def create(self, validated_data):
        from .device_operations import execute_device_operation
        request = self.context.get('request')
        return execute_device_operation(
            performed_by=request.user,
            **validated_data,
        )
