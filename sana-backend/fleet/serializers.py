from rest_framework import serializers
from django.db.models import Q
from django.utils import timezone
from .models import VehicleType, Vehicle, DeviceModel, Device, Driver, DriverVehicleAssignment, DeviceLifecycleEvent, DeviceReplacementRelation, DeviceOperation


class VehicleTypeSerializer(serializers.ModelSerializer):
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
        device = obj.devices.filter(management_status='active').first()
        return device.imei if device else None

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
        device = obj.devices.filter(management_status='active').first()
        if not device:
            return 'none'
        return device.management_status


class DeviceModelSerializer(serializers.ModelSerializer):
    devices_count = serializers.IntegerField(source='devices.count', read_only=True)

    class Meta:
        model = DeviceModel
        fields = ['id', 'manufacturer', 'name', 'code', 'protocol', 'devices_count', 'created_at']
        read_only_fields = ['id', 'created_at']

class DeviceSerializer(serializers.ModelSerializer):
    current_holder_organization_name = serializers.CharField(source='current_holder_organization.name', read_only=True)
    current_holder_user_name = serializers.CharField(source='current_holder_user.full_name', read_only=True)
    device_model_name = serializers.CharField(source='device_model.name', read_only=True)
    device_model_manufacturer = serializers.CharField(source='device_model.manufacturer', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    owner_name = serializers.CharField(source='owner_user.full_name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate', read_only=True)
    management_status = serializers.SerializerMethodField()

    def get_management_status(self, obj):
        if obj.is_in_warehouse:
            return 'warehouse'
        return obj.management_status

    class Meta:
        model = Device
        fields = [
            'id', 'imei',
            'device_model', 'device_model_name', 'device_model_manufacturer',
            'organization', 'organization_name',
            'owner_user', 'owner_name',
            'branch', 'branch_name',
            'current_holder_organization', 'current_holder_organization_name',
            'current_holder_user', 'current_holder_user_name',
            'vehicle', 'vehicle_plate',
            'sim_number',
            'management_status',
            'installed_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'organization': {'required': False, 'allow_null': True},
            'owner_user': {'required': False, 'allow_null': True},
            'vehicle': {'required': False, 'allow_null': True},
        }

    def create(self, validated_data):
        request = self.context.get('request')
        if request:
            user = request.user
            if user.account_type == 'organization' and user.organization_id:
                validated_data.setdefault('organization_id', user.organization_id)
            elif user.account_type == 'personal':
                validated_data['owner_user'] = user

        instance = super().create(validated_data)
        from .lifecycle import record_device_lifecycle_event
        record_device_lifecycle_event(
            device=instance,
            event_type='received',
            performed_by=self.context.get('request').user if self.context.get('request') else None,
            description='دستگاه به موجودی سانا اضافه شد.',
        )
        return instance

class DeviceListSerializer(serializers.ModelSerializer):
    management_status = serializers.SerializerMethodField()

    def get_management_status(self, obj):
        """اگه توی انباره، warehouse نشون بده"""
        if obj.is_in_warehouse:
            return 'warehouse'
        return obj.management_status

    device_model_name = serializers.CharField(source='device_model.name', read_only=True)
    device_model_manufacturer = serializers.CharField(source='device_model.manufacturer', read_only=True)
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

    # وضعیت انبار
    is_in_warehouse = serializers.BooleanField(read_only=True)

    class Meta:
        model = Device
        fields = [
            'id', 'imei',
            'device_model_name', 'device_model_manufacturer',
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
            'is_in_warehouse',
            'created_at',
        ]

    def get_customer_name(self, obj):
        # نمایش مشتری باید فقط به current_holder وابسته نباشد؛
        # دستگاه‌هایی که از مسیر قرارداد به مشتری تخصیص یافته‌اند
        # ممکن است مالکیتشان روی organization / owner_user ثبت شده باشد
        # ولی current_holder هنوز مقداردهی نشده باشد.
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
        """قرارداد قابل نمایش دستگاه را از وضعیت فعلی یا سابقه آن پیدا می‌کند.

        در دستگاه‌های جایگزین، ممکن است دستگاه قبلی دیگر اتصال فعال نداشته
        باشد؛ با این حال باید قرارداد مرتبط با سابقه دستگاه همچنان در لیست
        قابل مشاهده باشد.
        """
        active_link = obj.active_subscription_link
        if active_link:
            return active_link

        # اگر اتصال فعال بسته شده باشد، آخرین اتصال تاریخی دستگاه را نشان بده.
        historical_link = obj.subscription_links.select_related(
            'subscription'
        ).order_by('-assigned_at', '-id').first()
        if historical_link:
            return historical_link

        # پشتیبان برای داده‌های قدیمی/غیرهمگام که عملیات جایگزینی قرارداد
        # را ثبت کرده ولی SubscriptionDevice برای دستگاه موجود نیست.
        replacement_operation = obj.operations.filter(
            replacement_device__isnull=False,
            subscription__isnull=False,
            operation_type__in={
                'return_for_repair',
                'temporary_replacement',
                'permanent_replacement',
            },
        ).select_related('subscription').order_by(
            '-performed_at', '-id'
        ).first()
        if replacement_operation:
            return replacement_operation

        replacement_operation = obj.replacement_operations.filter(
            subscription__isnull=False,
            operation_type__in={
                'return_for_repair',
                'temporary_replacement',
                'permanent_replacement',
            },
        ).select_related('subscription').order_by(
            '-performed_at', '-id'
        ).first()
        if replacement_operation:
            return replacement_operation

        return None

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
        link = obj.active_subscription_link
        if not link:
            return None

        # B is the replacement device in the return-for-repair operation.
        # Match the operation to the currently active contract so an old
        # replacement history cannot affect the current device role.
        return obj.replacement_operations.filter(
            operation_type='return_for_repair',
            subscription=link.subscription,
        ).order_by('-performed_at', '-id').first()

    def get_subscription_device_type(self, obj):
        link = obj.active_subscription_link
        if not link:
            return None

        replacement_operation = self._current_replacement_operation(obj)
        if replacement_operation and replacement_operation.replacement_type:
            return replacement_operation.replacement_type

        # Fallback for existing records created before DeviceOperation was
        # linked consistently: the replacement relation still contains the
        # authoritative replacement type.
        relation = obj.replacement_relations_as_replacement.order_by(
            '-replacement_date', '-id'
        ).first()
        if relation:
            return relation.replacement_type

        # The source device remains in the contract after replacement.
        # While it is out of operation, show its relationship as «replaced»
        # instead of incorrectly presenting it as the current primary device.
        source_relation = obj.replacement_relations_as_source.order_by(
            '-replacement_date', '-id'
        ).first()
        if source_relation and obj.management_status in {
            'faulty', 'lost', 'stolen', 'ready'
        }:
            return 'replaced'

        return 'primary'

    def get_management_status(self, obj):
        if obj.is_in_warehouse:
            return 'warehouse'

        replacement_operation = self._current_replacement_operation(obj)
        if replacement_operation and replacement_operation.replacement_type:
            if replacement_operation.replacement_type == 'temporary_repair':
                return 'installed'
            if replacement_operation.replacement_type == 'permanent_replacement':
                return 'sold'

        return obj.management_status

    def get_subscription_device_type_display(self, obj):
        value = self.get_subscription_device_type(obj)
        return {
            'primary': 'دستگاه اصلی',
            'temporary_repair': 'جایگزین موقت',
            'permanent_replacement': 'جایگزین دائمی',
            'replacement': 'دستگاه جایگزین',
        'replaced': 'جایگزین شده',
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
            'replacement_type', 'replacement_method', 'outcome_action', 'reason', 'description',
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
