from rest_framework import serializers
from .models import VehicleType, Vehicle, DeviceModel, Device, Driver, DeviceLifecycleEvent, DeviceReplacementRelation, DeviceOperation


class VehicleTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleType
        fields = ['id', 'name', 'organization', 'created_at']
        read_only_fields = ['id', 'created_at']


class VehicleSerializer(serializers.ModelSerializer):
    vehicle_type_name = serializers.CharField(source='vehicle_type.name', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    current_holder_organization_name = serializers.CharField(source='current_holder_organization.name', read_only=True)
    current_holder_user_name = serializers.CharField(source='current_holder_user.full_name', read_only=True)
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

    # اطلاعات قرارداد فعلی
    subscription_id = serializers.SerializerMethodField()
    subscription_number = serializers.SerializerMethodField()
    subscription_end_date = serializers.SerializerMethodField()

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
            'vehicle_plate',
            'subscription_id', 'subscription_number', 'subscription_end_date',
            'management_status',
            'is_in_warehouse',
            'created_at',
        ]

    def get_subscription_id(self, obj):
        link = obj.active_subscription_link
        return link.subscription.id if link else None

    def get_subscription_number(self, obj):
        link = obj.active_subscription_link
        return link.subscription.contract_number if link else None

    def get_subscription_end_date(self, obj):
        link = obj.active_subscription_link
        return link.end_date if link else None

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
            'id', 'device', 'device_imei', 'event_type', 'event_type_display',
            'event_date', 'subscription', 'subscription_number',
            'organization', 'organization_name', 'user', 'user_name',
            'vehicle', 'vehicle_plate', 'branch', 'branch_name',
            'reason', 'reason_display', 'description',
            'previous_status', 'new_status', 'performed_by', 'performed_by_name',
            'created_at',
        ]
        read_only_fields = [
            'id', 'device_imei', 'event_type_display', 'reason_display',
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
