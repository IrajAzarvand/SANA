from rest_framework import serializers
from django.utils import timezone
from .models import (
    Organization,
    Branch,
    Subscription,
    SubscriptionDevice,
    SubscriptionPayment,
    SubscriptionOperation,
    SubscriptionOperationChange,
)


# ═══════════════════════════════════════════════
# Organization
# ═══════════════════════════════════════════════

class OrganizationSerializer(serializers.ModelSerializer):
    branches_count = serializers.IntegerField(source='branches.count', read_only=True)
    vehicles_count = serializers.IntegerField(source='vehicles.count', read_only=True)
    devices_count = serializers.IntegerField(source='devices.count', read_only=True)
    users_count = serializers.IntegerField(source='users.count', read_only=True)

    class Meta:
        model = Organization
        fields = [
            'id', 'name', 'code',
            'registration_number', 'economy_code',
            'phone', 'email', 'address', 'website', 'logo',
            'status',
            'branches_count', 'vehicles_count', 'devices_count', 'users_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class OrganizationListSerializer(serializers.ModelSerializer):
    branches_count = serializers.IntegerField(source='branches.count', read_only=True)
    vehicles_count = serializers.IntegerField(source='vehicles.count', read_only=True)
    devices_count = serializers.IntegerField(source='devices.count', read_only=True)

    class Meta:
        model = Organization
        fields = [
            'id', 'name', 'code', 'phone', 'status',
            'branches_count', 'vehicles_count', 'devices_count',
            'created_at',
        ]


# ═══════════════════════════════════════════════
# Branch
# ═══════════════════════════════════════════════

class BranchSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    vehicles_count = serializers.IntegerField(source='vehicles.count', read_only=True)
    devices_count = serializers.IntegerField(source='devices.count', read_only=True)
    drivers_count = serializers.IntegerField(source='drivers.count', read_only=True)

    class Meta:
        model = Branch
        fields = [
            'id', 'organization', 'organization_name',
            'name', 'code', 'phone', 'address', 'status',
            'vehicles_count', 'devices_count', 'drivers_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class BranchListSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    vehicles_count = serializers.IntegerField(source='vehicles.count', read_only=True)
    devices_count = serializers.IntegerField(source='devices.count', read_only=True)
    drivers_count = serializers.IntegerField(source='drivers.count', read_only=True)

    class Meta:
        model = Branch
        fields = [
            'id', 'organization', 'organization_name',
            'name', 'code', 'phone', 'status',
            'vehicles_count', 'devices_count', 'drivers_count',
            'created_at',
        ]


# ═══════════════════════════════════════════════
# SubscriptionDevice
# ═══════════════════════════════════════════════

class SubscriptionDeviceSerializer(serializers.ModelSerializer):
    device_imei = serializers.CharField(source='device.imei', read_only=True)
    device_model = serializers.CharField(source='device.device_model.name', read_only=True)
    device_model_manufacturer = serializers.CharField(source='device.device_model.manufacturer', read_only=True)
    device_sim = serializers.CharField(source='device.sim_number', read_only=True)
    vehicle_plate = serializers.CharField(source='device.vehicle.plate', read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)

    class Meta:
        model = SubscriptionDevice
        fields = [
            'id',
            'subscription',
            'device', 'device_imei', 'device_model', 'device_model_manufacturer', 'device_sim',
            'vehicle_plate',
            'start_date', 'end_date',
            'assigned_at', 'unassigned_at',
            'is_active', 'is_expired', 'days_until_expiry',
        ]
        read_only_fields = ['id', 'assigned_at', 'unassigned_at']

    def validate(self, data):
        # چک کن دستگاه قبلاً توی قرارداد فعال دیگه نباشه
        device = data.get('device')
        subscription = data.get('subscription')
        if device and self.instance is None:
            active_link = device.subscription_links.filter(unassigned_at__isnull=True).first()
            if active_link:
                raise serializers.ValidationError({
                    'device': f'دستگاه {device.imei} در قرارداد فعال دیگری است'
                })
        # چک تاریخ
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError({
                    'end_date': 'تاریخ پایان باید بعد از تاریخ شروع باشد'
                })
        return data

    def create(self, validated_data):
        # بعد از ساخت، مالکیت دستگاه رو هم به قرارداد اختصاص بده
        instance = super().create(validated_data)
        device = instance.device
        subscription = instance.subscription

        # اختصاص مالکیت
        if subscription.organization:
            device.organization = subscription.organization
            device.owner_user = None
        elif subscription.user:
            device.owner_user = subscription.user
            device.organization = None

        # آپدیت وضعیت
        if device.management_status == 'warehouse':
            device.management_status = 'sold'

        device.save()
        return instance

    
# ═══════════════════════════════════════════════
# SubscriptionPayment
# ═══════════════════════════════════════════════

class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPayment
        fields = [
            'id', 'subscription',
            'amount', 'payment_date', 'device_count', 'description', 'operation',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


# ═══════════════════════════════════════════════
# SubscriptionOperation
# ═══════════════════════════════════════════════

class SubscriptionOperationChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionOperationChange
        fields = ['id', 'entity_type', 'field_name', 'old_value', 'new_value']
        read_only_fields = ['id']


class SubscriptionOperationSerializer(serializers.ModelSerializer):
    operation_type_display = serializers.CharField(source='get_operation_type_display', read_only=True)
    performed_by_name = serializers.SerializerMethodField()
    changes = SubscriptionOperationChangeSerializer(many=True, read_only=True)
    added_device_ids = serializers.SerializerMethodField()
    removed_device_ids = serializers.SerializerMethodField()
    payment_ids = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionOperation
        fields = [
            'id', 'subscription', 'operation_type', 'operation_type_display',
            'performed_at', 'performed_by', 'performed_by_name',
            'old_start_date', 'new_start_date', 'old_end_date', 'new_end_date',
            'old_status', 'new_status', 'notes', 'changes', 'added_device_ids', 'removed_device_ids', 'payment_ids',
        ]
        read_only_fields = ['id', 'performed_at', 'performed_by']

    def get_added_device_ids(self, obj):
        return list(obj.added_devices.values_list('device_id', flat=True))

    def get_removed_device_ids(self, obj):
        return list(obj.removed_devices.values_list('device_id', flat=True))

    def get_payment_ids(self, obj):
        return list(obj.payments.values_list('id', flat=True))

    def get_performed_by_name(self, obj):
        if not obj.performed_by:
            return None
        return obj.performed_by.full_name or obj.performed_by.username


# Subscription
# ═══════════════════════════════════════════════

class SubscriptionSerializer(serializers.ModelSerializer):
    """سریالایزر کامل قرارداد با nested"""

    customer_name = serializers.CharField(source='get_customer_name', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    organization_code = serializers.CharField(source='organization.code', read_only=True)
    organization_phone = serializers.CharField(source='organization.phone', read_only=True)
    organization_email = serializers.CharField(source='organization.email', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)

    # status محاسبه‌شده
    status = serializers.CharField(source='computed_status', read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    is_expiring_soon = serializers.BooleanField(read_only=True)

    # فقط دستگاه‌های فعال (unassigned_at=None)
    devices = serializers.SerializerMethodField()
    payments = SubscriptionPaymentSerializer(many=True, read_only=True)
    operations = SubscriptionOperationSerializer(many=True, read_only=True)

    device_count = serializers.SerializerMethodField()


    class Meta:
        model = Subscription
        fields = [
            'id', 'contract_number',
            'customer_type',
            'organization', 'organization_name', 'organization_code',
            'organization_phone', 'organization_email',
            'user', 'user_name',
            'customer_name',
            'start_date', 'end_date',
            'price', 'status', 'notes',
            'days_until_expiry', 'is_active', 'is_expiring_soon',
            'device_count',
            'devices', 'payments', 'operations',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_devices(self, obj):
        """فقط لینک‌های فعال (unassigned_at=None) رو برگردون"""
        active_links = obj.subscription_devices.filter(unassigned_at__isnull=True)
        return SubscriptionDeviceSerializer(active_links, many=True).data

    def get_device_count(self, obj):
        return obj.subscription_devices.filter(unassigned_at__isnull=True).count()

class SubscriptionListSerializer(serializers.ModelSerializer):
    """سریالایزر سبک برای لیست"""

    customer_name = serializers.CharField(source='get_customer_name', read_only=True)
    status = serializers.CharField(source='computed_status', read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)
    is_expiring_soon = serializers.BooleanField(read_only=True)
    device_count = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            'id', 'contract_number',
            'customer_type',
            'customer_name',
            'start_date', 'end_date',
            'price', 'status',
            'days_until_expiry', 'is_expiring_soon', 'device_count',
        ]

    def get_device_count(self, obj):
        return obj.subscription_devices.filter(unassigned_at__isnull=True).count()


# ═══════════════════════════════════════════════
# Wizard — ساخت قرارداد یکجا
# ═══════════════════════════════════════════════

class SubscriptionWizardDeviceSerializer(serializers.Serializer):
    """اطلاعات یک دستگاه در Wizard"""
    device_id = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()


class SubscriptionWizardPaymentSerializer(serializers.Serializer):
    """اطلاعات یک پرداخت در Wizard"""
    amount = serializers.DecimalField(max_digits=15, decimal_places=0)
    payment_date = serializers.DateField()
    device_count = serializers.IntegerField(default=0)
    description = serializers.CharField(required=False, allow_blank=True)


class SubscriptionWizardSerializer(serializers.Serializer):
    """
    سریالایزر چندمنظوره برای ساخت قرارداد کامل با Wizard
    شامل: مشتری + قرارداد + دستگاه‌ها + پرداخت
    """

    # نوع مشتری
    customer_type = serializers.ChoiceField(choices=['organization', 'personal'])
    # انتخاب کاربر موجود (اختیاری)
    existing_user_id = serializers.IntegerField(required=False, allow_null=True)


    # اطلاعات مشتری (اگه سازمانی)
    organization_name = serializers.CharField(required=False, allow_blank=True)
    organization_code = serializers.CharField(required=False, allow_blank=True)
    registration_number = serializers.CharField(required=False, allow_blank=True)
    economy_code = serializers.CharField(required=False, allow_blank=True)
    organization_phone = serializers.CharField(required=False, allow_blank=True)
    organization_email = serializers.EmailField(required=False, allow_blank=True)
    organization_address = serializers.CharField(required=False, allow_blank=True)

    # اطلاعات کاربر (مدیر شرکت یا کاربر شخصی)
    username = serializers.CharField()
    password = serializers.CharField(min_length=8, write_only=True)
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    mobile = serializers.CharField()
    national_id = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)

    # اطلاعات قرارداد
    contract_number = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    notes = serializers.CharField(required=False, allow_blank=True)

    # دستگاه‌ها
    devices = SubscriptionWizardDeviceSerializer(many=True, default=list)

    # پرداخت
    payments = SubscriptionWizardPaymentSerializer(many=True, default=list)

    def validate_username(self, value):
        from accounts.models import User

        # اگه existing_user_id داریم، username از قبل ثبت شده — چک نکن
        if self.initial_data.get('existing_user_id'):
            return value

        # فقط وقتی که کاربر جدید می‌سازیم، یهتا بودن username رو چک کن
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('این نام کاربری قبلاً استفاده شده است')
        return value

    def validate_contract_number(self, value):
        if Subscription.objects.filter(contract_number=value).exists():
            raise serializers.ValidationError('این شماره قرارداد قبلاً استفاده شده است')
        return value

    def validate(self, data):
        existing_user_id = data.get('existing_user_id')

        # اگه کاربر موجود انتخاب شده، اطلاعات User جدید اجباری نیست
        if existing_user_id:
            from accounts.models import User
            try:
                user = User.objects.get(id=existing_user_id)
                # customer_type باید با account_type کاربر مطابقت داشته باشه
                if user.account_type != data['customer_type']:
                    raise serializers.ValidationError({
                        'existing_user_id': 'نوع حساب کاربر با نوع مشتری انتخاب‌شده مطابقت ندارد'
                    })
            except User.DoesNotExist:
                raise serializers.ValidationError({
                    'existing_user_id': 'کاربر انتخاب‌شده یافت نشد'
                })
        else:
            # چک: اگه سازمانی، اطلاعات سازمانی لازمه
            if data['customer_type'] == 'organization':
                if not data.get('organization_name'):
                    raise serializers.ValidationError({
                        'organization_name': 'نام سازمان الزامی است'
                    })

        # چک تاریخ
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError({
                'end_date': 'تاریخ پایان باید بعد از تاریخ شروع باشد'
            })

        # چک طول کد ملی
        national_id = data.get('national_id', '')
        if national_id and len(national_id) > 20:
            raise serializers.ValidationError({
                'national_id': 'کد ملی نباید بیشتر از ۲۰ کاراکتر باشد'
            })

        # چک طول موبایل
        mobile = data.get('mobile', '')
        if mobile and len(mobile) > 20:
            raise serializers.ValidationError({
                'mobile': 'موبایل نباید بیشتر از ۲۰ کاراکتر باشد'
            })

        # چک دستگاه‌ها
        for i, device_data in enumerate(data.get('devices', [])):
            if device_data['start_date'] > device_data['end_date']:
                raise serializers.ValidationError({
                    'devices': f'دستگاه {i+1}: تاریخ پایان باید بعد از تاریخ شروع باشد'
                })

        return data

    
    def create(self, validated_data):
        from accounts.models import User
        from fleet.models import Device
        from django.db import transaction

        devices_data = validated_data.pop('devices', [])
        payments_data = validated_data.pop('payments', [])
        customer_type = validated_data['customer_type']

        # ═══ DEBUG TEMP LINES═══
        print("=" * 60)
        print("📥 Payments received:", payments_data)
        print("📥 Devices received:", len(devices_data))
        print("=" * 60)
        # ═════════════

        with transaction.atomic():
            # ─── ۱. ساخت Organization (اگه سازمانی) ───
            organization = None
            if customer_type == 'organization':
                # تولید خودکار کد سازمان اگه داده نشده
                org_code = validated_data.get('organization_code', '').strip()
                if not org_code:
                    # تولید از username: ORG-{username.upper()}
                    org_code = f"ORG-{validated_data['username'].upper()}"
                    # چک کن تکراری نباشه
                    base_code = org_code
                    counter = 1
                    while Organization.objects.filter(code=org_code).exists():
                        counter += 1
                        org_code = f"{base_code}-{counter}"

                organization = Organization.objects.create(
                    name=validated_data['organization_name'],
                    code=org_code,
                    registration_number=validated_data.get('registration_number', ''),
                    economy_code=validated_data.get('economy_code', ''),
                    phone=validated_data.get('organization_phone', ''),
                    email=validated_data.get('organization_email', ''),
                    address=validated_data.get('organization_address', ''),
                    status='active',
                )

            # ─── ۲. ساخت User ───
            existing_user_id = validated_data.pop('existing_user_id', None)

            if existing_user_id:
                # کاربر موجود رو استفاده کن
                user = User.objects.get(id=existing_user_id)

                # اگه organization جدید ساخته شده (نوع سازمانی)، به User وصلش کن
                if organization and not user.organization_id:
                    user.organization = organization
                    user.save()
            else:
                # کاربر جدید بساز
                user = User.objects.create_user(
                    username=validated_data['username'],
                    password=validated_data['password'],
                    first_name=validated_data['first_name'],
                    last_name=validated_data['last_name'],
                    mobile=validated_data['mobile'],
                    national_id=validated_data.get('national_id', ''),
                    address=validated_data.get('address', ''),
                    account_type=customer_type,
                    role='main_user' if customer_type == 'organization' else 'personal_user',
                    organization=organization,
                )

            # ─── ۳. ساخت Subscription ───
            subscription = Subscription.objects.create(
                contract_number=validated_data['contract_number'],
                customer_type=customer_type,
                organization=organization,
                user=user if customer_type == 'personal' else None,
                start_date=validated_data['start_date'],
                end_date=validated_data['end_date'],
                notes=validated_data.get('notes', ''),
                status='active',
            )

            # ایجاد قرارداد خودش یک عملیات قابل حسابرسی است.
            operation = SubscriptionOperation.objects.create(
                subscription=subscription,
                operation_type='create',
                performed_by=self.context.get('request').user if self.context.get('request') else None,
                old_start_date=None,
                new_start_date=subscription.start_date,
                old_end_date=None,
                new_end_date=subscription.end_date,
                old_status='',
                new_status=subscription.status,
                notes=subscription.notes,
            )

            # ─── ۴. اضافه کردن دستگاه‌ها ───
            for device_data in devices_data:
                try:
                    device = Device.objects.get(id=device_data['device_id'])
                except Device.DoesNotExist:
                    raise serializers.ValidationError({
                        'devices': f'دستگاه با ID {device_data["device_id"]} یافت نشد'
                    })

                # چک: دستگاه نباید توی قرارداد فعال دیگه باشه
                active_link = device.subscription_links.filter(
                    unassigned_at__isnull=True
                ).first()
                if active_link:
                    raise serializers.ValidationError({
                        'devices': f'دستگاه {device.imei} در قرارداد فعال دیگری است'
                    })

                SubscriptionDevice.objects.create(
                    subscription=subscription,
                    device=device,
                    start_date=device_data['start_date'],
                    end_date=device_data['end_date'],
                    added_by_operation=operation,
                )

                # تخصیص مالکیت دستگاه
                if organization:
                    device.organization = organization
                else:
                    device.owner_user = user

                # آپدیت وضعیت مدیریتی دستگاه — از انبار خارج شد
                device.management_status = 'sold'
                device.save()

            # ─── ۵. اضافه کردن پرداخت‌ها ───
            for payment_data in payments_data:
                SubscriptionPayment.objects.create(
                    subscription=subscription,
                    amount=payment_data['amount'],
                    payment_date=payment_data['payment_date'],
                    device_count=payment_data.get('device_count', 0),
                    description=payment_data.get('description', ''),
                    operation=operation,
                )

            return subscription


