from rest_framework import serializers
from .models import VehicleType, Vehicle, DeviceModel, Device, Driver


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

        return super().create(validated_data)

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