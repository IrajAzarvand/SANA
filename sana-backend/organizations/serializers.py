from rest_framework import serializers
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from django.db.models import Sum
from fleet.lifecycle import record_device_lifecycle_event
from .models import (
    Organization,
    Branch,
    Subscription,
    SubscriptionDevice,
    SubscriptionPayment,
    SubscriptionInstallmentPlan,
    SubscriptionInstallment,
    SubscriptionPaymentAllocation,
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


class OrganizationSettingsSerializer(serializers.ModelSerializer):
    """Self-service organization profile; lifecycle and identifiers stay read-only."""

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
        read_only_fields = [
            'id', 'code', 'logo', 'status',
            'branches_count', 'vehicles_count', 'devices_count', 'users_count',
            'created_at', 'updated_at',
        ]


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
    device_model = serializers.CharField(source='device.device_model.name', read_only=True, allow_null=True)
    device_model_manufacturer = serializers.CharField(source='device.device_model.manufacturer', read_only=True, allow_null=True)
    device_sim = serializers.CharField(source='device.sim_number', read_only=True)
    vehicle_plate = serializers.CharField(source='device.vehicle.plate', read_only=True)
    management_status = serializers.CharField(source='device.management_status', read_only=True)
    management_status_display = serializers.CharField(
        source='device.get_management_status_display',
        read_only=True,
    )
    replacement_relation = serializers.SerializerMethodField()
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
            'management_status', 'management_status_display', 'replacement_relation',
            'start_date', 'end_date',
            'assigned_at', 'unassigned_at',
            'is_active', 'is_expired', 'days_until_expiry',
        ]
        read_only_fields = ['id', 'assigned_at', 'unassigned_at']

    def get_replacement_relation(self, obj):
        device = obj.device

        source_relations = list(device.replacement_relations_as_source.all())
        if source_relations:
            relation = source_relations[0]
            related = relation.replacement_device
            return {
                'direction': 'replaced',
                'label': 'جایگزین شده',
                'replacement_type': relation.replacement_type,
                'replacement_type_display': relation.get_replacement_type_display(),
                'related_device_id': related.id,
                'related_device_imei': related.imei,
                'related_device_model': related.device_model.name if related.device_model else None,
                'related_device_sim': related.sim_number,
                'related_device_status': related.management_status,
                'related_device_status_display': related.get_management_status_display(),
            }

        replacement_relations = list(device.replacement_relations_as_replacement.all())
        if replacement_relations:
            relation = replacement_relations[0]
            related = relation.source_device
            label = (
                'جایگزین موقت'
                if relation.replacement_type == 'temporary_repair'
                else 'تعویض دائمی'
            )
            return {
                'direction': 'replacement',
                'label': label,
                'replacement_type': relation.replacement_type,
                'replacement_type_display': relation.get_replacement_type_display(),
                'related_device_id': related.id,
                'related_device_imei': related.imei,
                'related_device_model': related.device_model.name if related.device_model else None,
                'related_device_sim': related.sim_number,
                'related_device_status': related.management_status,
                'related_device_status_display': related.get_management_status_display(),
            }

        return None

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
        # چک ترتیب تاریخ‌ها
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError({
                    'end_date': 'تاریخ پایان باید بعد از تاریخ شروع باشد'
                })

        # هر دستگاه قرارداد باید کاملاً داخل بازه قرارداد باشد.
        if subscription and data.get('start_date') and data.get('end_date'):
            if data['start_date'] < subscription.start_date:
                raise serializers.ValidationError({
                    'start_date': 'تاریخ شروع دستگاه نمی‌تواند قبل از شروع قرارداد باشد'
                })
            if data['end_date'] > subscription.end_date:
                raise serializers.ValidationError({
                    'end_date': 'تاریخ پایان دستگاه نمی‌تواند بعد از پایان قرارداد باشد'
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
            device.current_holder_organization = subscription.organization
            device.current_holder_user = None
        elif subscription.user:
            device.owner_user = subscription.user
            device.organization = None
            device.current_holder_organization = None
            device.current_holder_user = subscription.user

        # آپدیت وضعیت
        if device.management_status == 'warehouse':
            device.management_status = 'sold'

        device.save()
        request = self.context.get('request')
        record_device_lifecycle_event(
            device=device,
            event_type='assigned_to_contract',
            performed_by=request.user if request else None,
            subscription=subscription,
            description=f'دستگاه به قرارداد {subscription.contract_number} اضافه شد.',
        )
        return instance

    
# ═══════════════════════════════════════════════
# SubscriptionPayment
# ═══════════════════════════════════════════════

class SubscriptionPaymentAllocationSerializer(serializers.ModelSerializer):
    installment_number = serializers.IntegerField(source='installment.number', read_only=True)
    due_date = serializers.DateField(source='installment.due_date', read_only=True)

    class Meta:
        model = SubscriptionPaymentAllocation
        fields = ['id', 'allocation_type', 'installment', 'installment_number', 'due_date', 'amount', 'created_at']
        read_only_fields = fields


class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    payment_date = serializers.DateField(source='received_at')
    allocations = SubscriptionPaymentAllocationSerializer(many=True, read_only=True)
    unallocated_amount = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionPayment
        fields = [
            'id', 'subscription', 'amount', 'payment_date',
            'description', 'operation', 'allocations', 'unallocated_amount', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'allocations', 'unallocated_amount']
        extra_kwargs = {'amount': {'min_value': 1}}

    def validate_payment_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError('تاریخ دریافت وجه نمی‌تواند در آینده باشد')
        return value

    def get_unallocated_amount(self, obj):
        from django.db.models import Sum
        from decimal import Decimal
        allocated = obj.allocations.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        return max(Decimal(obj.amount) - allocated, Decimal('0'))


class SubscriptionInstallmentSerializer(serializers.ModelSerializer):
    paid_amount = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionInstallment
        fields = ['id', 'number', 'amount', 'due_date', 'status', 'paid_amount', 'remaining_amount', 'is_overdue']
        read_only_fields = fields

    def get_paid_amount(self, obj):
        from django.db.models import Sum
        return obj.allocations.aggregate(total=Sum('amount'))['total'] or 0

    def get_remaining_amount(self, obj):
        from .financial import installment_remaining_amount
        return installment_remaining_amount(obj)

    def get_is_overdue(self, obj):
        return obj.due_date < timezone.localdate() and self.get_remaining_amount(obj) > 0


class SubscriptionInstallmentPlanSerializer(serializers.ModelSerializer):
    installments = SubscriptionInstallmentSerializer(many=True, read_only=True)

    class Meta:
        model = SubscriptionInstallmentPlan
        fields = [
            'id', 'version', 'scheduled_amount', 'installment_count',
            'interval_months', 'calculation_mode', 'surplus_policy',
            'status', 'created_at', 'created_by', 'installments',
        ]
        read_only_fields = fields


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
    added_devices = serializers.SerializerMethodField()
    removed_devices = serializers.SerializerMethodField()
    payments = SubscriptionPaymentSerializer(many=True, read_only=True)

    class Meta:
        model = SubscriptionOperation
        fields = [
            'id', 'subscription', 'operation_type', 'operation_type_display',
            'performed_at', 'performed_by', 'performed_by_name',
            'old_start_date', 'new_start_date', 'old_end_date', 'new_end_date',
            'old_status', 'new_status', 'notes', 'changes',
            'added_devices', 'removed_devices', 'payments',
        ]
        read_only_fields = ['id', 'performed_at', 'performed_by']

    def _serialize_device_links(self, links):
        return [
            {
                'id': link.id,
                'device_id': link.device_id,
                'device_imei': link.device.imei,
                'device_model': link.device.device_model.name if link.device.device_model else None,
                'device_sim': link.device.sim_number,
                'vehicle_plate': link.device.vehicle.plate if link.device.vehicle else None,
                'start_date': link.start_date,
                'end_date': link.end_date,
                'assigned_at': link.assigned_at,
                'unassigned_at': link.unassigned_at,
            }
            for link in links.select_related('device__device_model', 'device__vehicle').all()
        ]

    def get_added_devices(self, obj):
        return self._serialize_device_links(obj.added_devices)

    def get_removed_devices(self, obj):
        return self._serialize_device_links(obj.removed_devices)

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
    user_mobile = serializers.CharField(source='user.mobile', read_only=True)
    user_national_id = serializers.CharField(source='user.national_id', read_only=True)
    user_address = serializers.CharField(source='user.address', read_only=True)
    organization_registration_number = serializers.CharField(source='organization.registration_number', read_only=True)
    organization_economy_code = serializers.CharField(source='organization.economy_code', read_only=True)
    organization_address = serializers.CharField(source='organization.address', read_only=True)

    # status محاسبه‌شده
    status = serializers.CharField(source='computed_status', read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    is_expiring_soon = serializers.BooleanField(read_only=True)

    # فقط دستگاه‌های فعال (unassigned_at=None)
    devices = serializers.SerializerMethodField()
    payments = SubscriptionPaymentSerializer(many=True, read_only=True)
    operations = SubscriptionOperationSerializer(many=True, read_only=True)
    installment_plan = serializers.SerializerMethodField()
    installment_plan_history = serializers.SerializerMethodField()

    device_count = serializers.SerializerMethodField()
    active_device_count = serializers.SerializerMethodField()
    total_payment_amount = serializers.SerializerMethodField()
    paid_payment_amount = serializers.SerializerMethodField()
    future_payment_amount = serializers.SerializerMethodField()
    outstanding_payment_amount = serializers.SerializerMethodField()
    overdue_balance = serializers.SerializerMethodField()
    future_due_balance = serializers.SerializerMethodField()
    unallocated_credit = serializers.SerializerMethodField()


    class Meta:
        model = Subscription
        fields = [
            'id', 'contract_number',
            'customer_type',
            'organization', 'organization_name', 'organization_code',
            'organization_phone', 'organization_email',
            'user', 'user_name', 'user_mobile', 'user_national_id', 'user_address',
            'organization_registration_number', 'organization_economy_code', 'organization_address',
            'customer_name',
            'start_date', 'end_date',
            'price', 'status', 'notes',
            'days_until_expiry', 'is_active', 'is_expiring_soon',
            'device_count', 'active_device_count',
            'total_payment_amount', 'paid_payment_amount', 'future_payment_amount',
            'outstanding_payment_amount', 'overdue_balance',
            'future_due_balance', 'unallocated_credit', 'installment_plan', 'installment_plan_history',
            'devices', 'payments', 'operations',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_devices(self, obj):
        """فقط لینک‌های فعال (unassigned_at=None) رو برگردون"""
        active_links = (
            obj.subscription_devices
            .filter(unassigned_at__isnull=True)
            .select_related('device__device_model', 'device__vehicle')
            .prefetch_related(
                'device__replacement_relations_as_source__replacement_device__device_model',
                'device__replacement_relations_as_replacement__source_device__device_model',
            )
        )
        return SubscriptionDeviceSerializer(active_links, many=True).data

    def get_device_count(self, obj):
        return obj.subscription_devices.filter(unassigned_at__isnull=True).count()

    def get_active_device_count(self, obj):
        return sum(
            1 for link in obj.subscription_devices.filter(unassigned_at__isnull=True)
            if link.is_active
        )

    def get_total_payment_amount(self, obj):
        return sum((payment.amount or 0) for payment in obj.payments.all())

    def get_paid_payment_amount(self, obj):
        return self.get_total_payment_amount(obj)

    def get_future_payment_amount(self, obj):
        today = timezone.localdate()
        plan = obj.installment_plans.filter(status='active').first()
        if not plan:
            return 0
        return sum(
            max(installment.amount - (installment.allocations.aggregate(total=Sum('amount'))['total'] or 0), 0)
            for installment in plan.installments.filter(status='active', due_date__gt=today)
        )

    def get_outstanding_payment_amount(self, obj):
        return max(obj.price - self.get_total_payment_amount(obj), 0)

    def get_installment_plan(self, obj):
        plan = obj.installment_plans.filter(status='active').prefetch_related('installments__allocations').first()
        return SubscriptionInstallmentPlanSerializer(plan).data if plan else None

    def get_installment_plan_history(self, obj):
        plans = obj.installment_plans.prefetch_related('installments__allocations').order_by('-version')
        return SubscriptionInstallmentPlanSerializer(plans, many=True).data

    def _remaining_by_due(self, obj, overdue):
        from django.db.models import Sum
        today = timezone.localdate()
        plan = obj.installment_plans.filter(status='active').first()
        if not plan:
            return 0
        qs = plan.installments.filter(status='active')
        qs = qs.filter(due_date__lt=today) if overdue else qs.filter(due_date__gte=today)
        total = 0
        for installment in qs:
            allocated = installment.allocations.aggregate(value=Sum('amount'))['value'] or 0
            total += max(installment.amount - allocated, 0)
        return total

    def get_overdue_balance(self, obj):
        return self._remaining_by_due(obj, True)

    def get_future_due_balance(self, obj):
        return self._remaining_by_due(obj, False)

    def get_unallocated_credit(self, obj):
        from django.db.models import Sum
        from decimal import Decimal
        receipts = obj.payments.aggregate(value=Sum('amount'))['value'] or Decimal('0')
        allocations = SubscriptionPaymentAllocation.objects.filter(
            payment__subscription=obj
        ).aggregate(value=Sum('amount'))['value'] or Decimal('0')
        return max(receipts - allocations, Decimal('0'))

class SubscriptionListSerializer(serializers.ModelSerializer):
    """سریالایزر سبک برای لیست"""

    customer_name = serializers.CharField(source='get_customer_name', read_only=True)
    status = serializers.CharField(source='computed_status', read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)
    is_expiring_soon = serializers.BooleanField(read_only=True)
    device_count = serializers.SerializerMethodField()
    active_device_count = serializers.SerializerMethodField()
    total_payment_amount = serializers.SerializerMethodField()
    paid_payment_amount = serializers.SerializerMethodField()
    future_payment_amount = serializers.SerializerMethodField()
    outstanding_payment_amount = serializers.SerializerMethodField()
    overdue_balance = serializers.SerializerMethodField()
    future_due_balance = serializers.SerializerMethodField()
    unallocated_credit = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            'id', 'contract_number',
            'customer_type',
            'customer_name',
            'start_date', 'end_date',
            'price', 'status',
            'days_until_expiry', 'is_expiring_soon',
            'device_count', 'active_device_count',
            'total_payment_amount', 'paid_payment_amount',
            'future_payment_amount', 'outstanding_payment_amount',
            'overdue_balance', 'future_due_balance', 'unallocated_credit',
        ]

    def get_device_count(self, obj):
        return obj.subscription_devices.filter(unassigned_at__isnull=True).count()

    def get_active_device_count(self, obj):
        today = timezone.now().date()
        return obj.subscription_devices.filter(
            unassigned_at__isnull=True,
            start_date__lte=today,
            end_date__gte=today,
        ).count()

    def get_total_payment_amount(self, obj):
        return sum((payment.amount or 0) for payment in obj.payments.all())

    def get_paid_payment_amount(self, obj):
        return self.get_total_payment_amount(obj)

    def get_future_payment_amount(self, obj):
        plan = obj.installment_plans.filter(status='active').first()
        if not plan:
            return 0
        return sum(
            max(item.amount - (item.allocations.aggregate(value=Sum('amount'))['value'] or 0), 0)
            for item in plan.installments.filter(status='active', due_date__gt=timezone.localdate())
        )

    def get_outstanding_payment_amount(self, obj):
        return max(obj.price - self.get_total_payment_amount(obj), 0)

    def get_overdue_balance(self, obj):
        from django.db.models import Sum
        plan = obj.installment_plans.filter(status='active').first()
        if not plan:
            return 0
        return sum(
            max(item.amount - (item.allocations.aggregate(value=Sum('amount'))['value'] or 0), 0)
            for item in plan.installments.filter(status='active', due_date__lt=timezone.localdate())
        )

    def get_future_due_balance(self, obj):
        from django.db.models import Sum
        plan = obj.installment_plans.filter(status='active').first()
        if not plan:
            return 0
        total = 0
        for item in plan.installments.filter(status='active', due_date__gte=timezone.localdate()):
            allocated = item.allocations.aggregate(value=Sum('amount'))['value'] or 0
            total += max(item.amount - allocated, 0)
        return total

    def get_unallocated_credit(self, obj):
        from django.db.models import Sum
        from decimal import Decimal
        receipts = obj.payments.aggregate(value=Sum('amount'))['value'] or Decimal('0')
        allocations = SubscriptionPaymentAllocation.objects.filter(payment__subscription=obj).aggregate(value=Sum('amount'))['value'] or Decimal('0')
        return max(receipts - allocations, Decimal('0'))


# ═══════════════════════════════════════════════
# Wizard — ساخت قرارداد یکجا
# ═══════════════════════════════════════════════

class SubscriptionWizardDeviceSerializer(serializers.Serializer):
    """اطلاعات یک دستگاه در Wizard"""
    device_id = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()


class SubscriptionWizardPaymentSerializer(serializers.Serializer):
    """دریافتی واقعی هنگام عقد قرارداد"""
    amount = serializers.DecimalField(max_digits=15, decimal_places=0, min_value=1)
    payment_date = serializers.DateField()
    description = serializers.CharField(required=False, allow_blank=True)

    def validate_payment_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError('تاریخ دریافت وجه نمی‌تواند در آینده باشد')
        return value


class SubscriptionWizardSerializer(serializers.Serializer):
    """
    سریالایزر چندمنظوره برای ساخت قرارداد کامل با Wizard
    شامل: مشتری + قرارداد + دستگاه‌ها + پرداخت
    """

    # نوع مشتری
    customer_type = serializers.ChoiceField(choices=['organization', 'personal'])
    # انتخاب کاربر موجود (اختیاری)
    existing_user_id = serializers.IntegerField(required=False, allow_null=True)
    # انتخاب سازمان موجود مستقل از انتخاب مدیر شرکت است.
    organization_id = serializers.IntegerField(required=False, allow_null=True)


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
    password = serializers.CharField(min_length=8, write_only=True, required=False)
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    mobile = serializers.CharField()
    national_id = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)

    # اطلاعات قرارداد
    contract_number = serializers.CharField()
    price = serializers.DecimalField(
        max_digits=15, decimal_places=0, min_value=1, required=True
    )
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    notes = serializers.CharField(required=False, allow_blank=True)

    # دستگاه‌ها
    devices = SubscriptionWizardDeviceSerializer(many=True, default=list)

    # پرداخت
    payments = SubscriptionWizardPaymentSerializer(many=True, default=list)
    installment_plan = serializers.JSONField(required=False, allow_null=True)

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
        from accounts.models import User

        customer_type = data['customer_type']
        existing_user_id = data.get('existing_user_id')
        organization_id = data.get('organization_id')
        selected_user = None
        selected_organization = None

        if customer_type == 'organization':
            if organization_id:
                try:
                    selected_organization = Organization.objects.get(id=organization_id)
                except Organization.DoesNotExist:
                    raise serializers.ValidationError({
                        'organization_id': 'سازمان انتخاب‌شده یافت نشد'
                    })
                if not data.get('organization_name', selected_organization.name).strip():
                    raise serializers.ValidationError({
                        'organization_name': 'نام سازمان الزامی است'
                    })
            elif not data.get('organization_name', '').strip():
                raise serializers.ValidationError({
                    'organization_name': 'برای ساخت سازمان جدید، نام سازمان الزامی است'
                })
        elif organization_id:
            raise serializers.ValidationError({
                'organization_id': 'برای مشتری شخصی نباید سازمان انتخاب شود'
            })

        if existing_user_id:
            try:
                selected_user = User.objects.select_related('organization').get(id=existing_user_id)
            except User.DoesNotExist:
                raise serializers.ValidationError({
                    'existing_user_id': 'کاربر انتخاب‌شده یافت نشد'
                })

            if selected_user.account_type != customer_type:
                raise serializers.ValidationError({
                    'existing_user_id': 'نوع حساب کاربر با نوع مشتری انتخاب‌شده مطابقت ندارد'
                })
            if customer_type == 'organization' and selected_user.role != 'main_user':
                raise serializers.ValidationError({
                    'existing_user_id': 'کاربر انتخاب‌شده مدیر اصلی یک سازمان نیست'
                })
            if selected_user.username != data.get('username'):
                raise serializers.ValidationError({
                    'username': 'نام کاربری با حساب انتخاب‌شده مطابقت ندارد'
                })

            if customer_type == 'organization':
                if selected_organization:
                    if selected_user.organization_id and selected_user.organization_id != selected_organization.id:
                        raise serializers.ValidationError({
                            'existing_user_id': 'مدیر انتخاب‌شده عضو سازمان دیگری است؛ برای جلوگیری از جابه‌جایی ناخواسته، مدیر دیگری انتخاب کنید'
                        })
                elif selected_user.organization_id:
                    raise serializers.ValidationError({
                        'organization_id': 'مدیر انتخاب‌شده به یک سازمان موجود متصل است؛ همان سازمان را انتخاب کنید'
                    })
        else:
            if not data.get('password'):
                raise serializers.ValidationError({
                    'password': 'برای ساخت حساب جدید، رمز عبور الزامی است'
                })

        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError({
                'end_date': 'تاریخ پایان باید بعد از تاریخ شروع باشد'
            })

        contract_price = data.get('price', 0)
        initial_receipts = sum((item['amount'] for item in data.get('payments', [])), 0)
        plan_data = data.get('installment_plan')
        if plan_data:
            scheduled_amount = contract_price - initial_receipts
            if scheduled_amount <= 0:
                raise serializers.ValidationError({
                    'installment_plan': 'پس از کسر پیش‌پرداخت، مبلغی برای تقسیط باقی نمانده است'
                })
            plan_data = dict(plan_data)
            plan_data['scheduled_amount'] = scheduled_amount
            mode = plan_data.get('calculation_mode', 'equal')
            try:
                count = int(plan_data.get('installment_count') or 0)
                interval = int(plan_data.get('interval_months') or 0)
            except (TypeError, ValueError):
                raise serializers.ValidationError({'installment_plan': 'تعداد و فاصله اقساط باید عدد صحیح باشند'})
            if not 1 <= count <= 120:
                raise serializers.ValidationError({'installment_plan': 'تعداد اقساط باید بین ۱ تا ۱۲۰ باشد'})
            if not 1 <= interval <= 120:
                raise serializers.ValidationError({'installment_plan': 'فاصله اقساط باید بین ۱ تا ۱۲۰ ماه باشد'})
            if mode == 'custom':
                custom = plan_data.get('custom_amounts') or []
                try:
                    custom_values = [Decimal(str(value)) for value in custom]
                except (InvalidOperation, TypeError, ValueError):
                    raise serializers.ValidationError({'installment_plan': 'مبالغ دلخواه اقساط نامعتبر هستند'})
                if (
                    len(custom_values) != count
                    or any(value <= 0 or value != value.to_integral_value() for value in custom_values)
                    or sum(custom_values, Decimal('0')) != scheduled_amount
                ):
                    raise serializers.ValidationError({'installment_plan': 'مبالغ دلخواه باید عدد صحیح و مثبت باشند و مجموعشان دقیقاً برابر مانده قرارداد باشد'})
            elif mode != 'equal':
                raise serializers.ValidationError({'installment_plan': 'روش محاسبه اقساط نامعتبر است'})
            if plan_data.get('surplus_policy', 'credit') not in ('credit', 'future'):
                raise serializers.ValidationError({'installment_plan': 'نحوه مدیریت مازاد دریافتی نامعتبر است'})

        national_id = data.get('national_id', '')
        if national_id and len(national_id) > 20:
            raise serializers.ValidationError({
                'national_id': 'کد ملی نباید بیشتر از ۲۰ کاراکتر باشد'
            })

        mobile = data.get('mobile', '')
        if mobile and len(mobile) > 20:
            raise serializers.ValidationError({
                'mobile': 'موبایل نباید بیشتر از ۲۰ کاراکتر باشد'
            })

        from fleet.models import Device

        devices_data = data.get('devices', [])
        if not devices_data:
            raise serializers.ValidationError({
                'devices': 'برای ثبت قرارداد، انتخاب حداقل یک دستگاه الزامی است'
            })

        device_ids = [item['device_id'] for item in devices_data]
        if len(device_ids) != len(set(device_ids)):
            raise serializers.ValidationError({
                'devices': 'یک دستگاه را بیش از یک بار انتخاب کرده‌اید'
            })

        devices_by_id = Device.objects.in_bulk(device_ids)
        for i, device_data in enumerate(devices_data):
            device_id = device_data['device_id']
            device = devices_by_id.get(device_id)
            if not device:
                raise serializers.ValidationError({
                    'devices': f'دستگاه با شناسه {device_id} یافت نشد'
                })

            if device_data['start_date'] > device_data['end_date']:
                raise serializers.ValidationError({
                    'devices': f'دستگاه {i+1}: تاریخ پایان باید بعد از تاریخ شروع باشد'
                })
            if (
                device_data['start_date'] < data['start_date']
                or device_data['end_date'] > data['end_date']
            ):
                raise serializers.ValidationError({
                    'devices': f'بازه زمانی دستگاه {device.imei} باید داخل بازه قرارداد باشد'
                })

            if device.management_status != 'warehouse':
                raise serializers.ValidationError({
                    'devices': f'دستگاه {device.imei} در وضعیت انبار نیست و قابل تخصیص به قرارداد جدید نیست'
                })
            if device.subscription_links.filter(unassigned_at__isnull=True).exists():
                raise serializers.ValidationError({
                    'devices': f'دستگاه {device.imei} قبلاً به یک قرارداد فعال متصل شده است'
                })

        return data

    
    def create(self, validated_data):
        from accounts.models import User
        from fleet.models import Device
        from django.db import transaction
        from .financial import allocate_payment, create_installment_plan

        devices_data = validated_data.pop('devices', [])
        payments_data = validated_data.pop('payments', [])
        installment_plan_data = validated_data.pop('installment_plan', None)
        customer_type = validated_data['customer_type']

        with transaction.atomic():
            # قفل‌کردن دستگاه‌ها و بررسی دوباره وضعیت انبار داخل تراکنش؛
            # این بررسی جلوی تخصیص هم‌زمان یک دستگاه در دو Wizard را می‌گیرد.
            device_ids = [item['device_id'] for item in devices_data]
            locked_devices = {
                device.pk: device
                for device in Device.objects.select_for_update()
                .filter(pk__in=device_ids)
                .order_by('pk')
            }
            if len(locked_devices) != len(set(device_ids)):
                raise serializers.ValidationError({
                    'devices': 'یک یا چند دستگاه انتخاب‌شده دیگر در سامانه وجود ندارند'
                })

            for device_id in device_ids:
                device = locked_devices[device_id]
                if device.management_status != 'warehouse':
                    raise serializers.ValidationError({
                        'devices': f'دستگاه {device.imei} دیگر در انبار موجود نیست'
                    })
                if device.subscription_links.filter(unassigned_at__isnull=True).exists():
                    raise serializers.ValidationError({
                        'devices': f'دستگاه {device.imei} در این فاصله به قرارداد دیگری متصل شده است'
                    })

            # ─── ۱. انتخاب یا ساخت Organization ───
            organization = None
            organization_id = validated_data.pop('organization_id', None)
            if customer_type == 'organization':
                if organization_id:
                    organization = Organization.objects.select_for_update().get(id=organization_id)
                    organization_fields = {
                        'name': validated_data.get('organization_name', organization.name),
                        'registration_number': validated_data.get('registration_number', organization.registration_number),
                        'economy_code': validated_data.get('economy_code', organization.economy_code),
                        'phone': validated_data.get('organization_phone', organization.phone),
                        'email': validated_data.get('organization_email', organization.email),
                        'address': validated_data.get('organization_address', organization.address),
                    }
                    for field, value in organization_fields.items():
                        setattr(organization, field, value)
                    organization.save(update_fields=list(organization_fields.keys()) + ['updated_at'])
                else:
                    org_code = validated_data.get('organization_code', '').strip()
                    if not org_code:
                        org_code = f"ORG-{validated_data['username'].upper()}"
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
                # حساب موجود حفظ می‌شود؛ فقط اطلاعات مجاز فرم به‌روزرسانی می‌شوند.
                # رمز عبور عمداً دست‌نخورده باقی می‌ماند.
                user = User.objects.select_for_update().get(id=existing_user_id)
                editable_fields = (
                    'first_name', 'last_name', 'mobile', 'national_id', 'address',
                )
                changed_fields = []
                for field in editable_fields:
                    if field in validated_data:
                        value = validated_data[field]
                        if getattr(user, field) != value:
                            setattr(user, field, value)
                            changed_fields.append(field)
                if changed_fields:
                    user.save(update_fields=changed_fields)

                # مدیر موجود فقط در صورت نداشتن سازمان به سازمان انتخاب‌شده وصل می‌شود.
                # انتقال از یک سازمان به سازمان دیگر عمداً مجاز نیست.
                if organization:
                    if user.organization_id and user.organization_id != organization.id:
                        raise serializers.ValidationError({
                            'existing_user_id': 'مدیر انتخاب‌شده عضو سازمان دیگری است'
                        })
                    if not user.organization_id:
                        user.organization = organization
                        user.save(update_fields=['organization'])
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
                price=validated_data.get('price', 0),
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
                device = locked_devices[device_data['device_id']]

                SubscriptionDevice.objects.create(
                    subscription=subscription,
                    device=device,
                    start_date=device_data['start_date'],
                    end_date=device_data['end_date'],
                    added_by_operation=operation,
                )

                # تخصیص مالکیت و مشتری فعلی دستگاه
                if organization:
                    device.organization = organization
                    device.owner_user = None
                    device.current_holder_organization = organization
                    device.current_holder_user = None
                else:
                    device.owner_user = user
                    device.organization = None
                    device.current_holder_organization = None
                    device.current_holder_user = user

                # آپدیت وضعیت مدیریتی دستگاه — از انبار خارج شد
                device.management_status = 'sold'
                device.save()
                record_device_lifecycle_event(
                    device=device,
                    event_type='assigned_to_contract',
                    performed_by=self.context.get('request').user if self.context.get('request') else None,
                    subscription=subscription,
                    description=f'دستگاه به قرارداد {subscription.contract_number} اضافه شد.',
                )

            # ─── ۵. ثبت دریافتی‌های واقعی زمان عقد قرارداد ───
            advance_remaining = subscription.price
            for payment_data in payments_data:
                payment = SubscriptionPayment.objects.create(
                    subscription=subscription,
                    amount=payment_data['amount'],
                    received_at=payment_data['payment_date'],
                    description=payment_data.get('description', ''),
                    operation=operation,
                )
                # پیش‌پرداخت فقط تا سقف مبلغ قرارداد اعمال می‌شود؛ اضافه آن اعتبار می‌ماند.
                advance_amount = min(payment.amount, max(advance_remaining, 0))
                allocate_payment(
                    payment,
                    allocation_type='contract_advance',
                    allocation_amount=advance_amount,
                )
                advance_remaining -= advance_amount

            # ─── ۶. ساخت نسخه اول برنامه اقساط ───
            if installment_plan_data:
                installment_plan_data['scheduled_amount'] = (
                    subscription.price - sum((item['amount'] for item in payments_data), 0)
                )
                create_installment_plan(
                    subscription,
                    installment_plan_data,
                    created_by=self.context.get('request').user if self.context.get('request') else None,
                )

            return subscription


