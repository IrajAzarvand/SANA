from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from rest_framework import viewsets, filters, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    Organization,
    Branch,
    Subscription,
    SubscriptionDevice,
    SubscriptionPayment,
    SubscriptionOperation,
    SubscriptionOperationChange,
)
from .serializers import (
    OrganizationSerializer,
    OrganizationListSerializer,
    BranchSerializer,
    BranchListSerializer,
    SubscriptionSerializer,
    SubscriptionListSerializer,
    SubscriptionWizardSerializer,
    SubscriptionDeviceSerializer,
    SubscriptionPaymentSerializer,
    SubscriptionOperationSerializer,
)
from accounts.permissions import IsSiteAdmin


# ═══════════════════════════════════════════════
# Organization
# ═══════════════════════════════════════════════

class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'registration_number']
    ordering_fields = ['name', 'created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return OrganizationListSerializer
        return OrganizationSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_site_admin:
            return Organization.objects.all()
        if user.organization_id:
            return Organization.objects.filter(id=user.organization_id)
        return Organization.objects.none()

    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            return [IsSiteAdmin()]
        return super().get_permissions()


# ═══════════════════════════════════════════════
# Branch
# ═══════════════════════════════════════════════

class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.select_related('organization').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return BranchListSerializer
        return BranchSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Branch.objects.select_related('organization')

        if user.is_site_admin:
            pass
        elif user.is_main_user and user.organization_id:
            qs = qs.filter(organization_id=user.organization_id)
        elif user.is_branch_manager and user.branch_id:
            qs = qs.filter(id=user.branch_id)
        else:
            qs = qs.none()

        org = self.request.query_params.get('organization')
        if org:
            qs = qs.filter(organization_id=org)

        return qs


# ═══════════════════════════════════════════════
# Subscription
# ═══════════════════════════════════════════════

class SubscriptionViewSet(viewsets.ModelViewSet):
    queryset = Subscription.objects.select_related('organization', 'user').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['contract_number', 'organization__name', 'user__username']
    ordering_fields = ['created_at', 'end_date', 'start_date']

    def get_serializer_class(self):
        if self.action == 'list':
            return SubscriptionListSerializer
        if self.action == 'create':
            return SubscriptionWizardSerializer
        return SubscriptionSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Subscription.objects.select_related('organization', 'user')

        if user.is_site_admin:
            pass
        elif user.organization_id:
            qs = qs.filter(organization_id=user.organization_id)
        elif user.is_personal_user:
            qs = qs.filter(user=user)
        else:
            qs = qs.none()

        # فیلترها
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        customer_type = self.request.query_params.get('customer_type')
        if customer_type:
            qs = qs.filter(customer_type=customer_type)

        expiring = self.request.query_params.get('expiring')
        if expiring == 'true':
            today = timezone.now().date()
            thirty_days = today + timedelta(days=30)
            qs = qs.filter(
                status='active',
                end_date__gte=today,
                end_date__lte=thirty_days,
            )

        return qs

    def get_permissions(self):
        if self.action in ['create', 'destroy', 'renew']:
            return [IsSiteAdmin()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        """ساخت قرارداد با Wizard"""
        serializer = SubscriptionWizardSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        subscription = serializer.save()

        # برگرداندن اطلاعات کامل
        response_serializer = SubscriptionSerializer(subscription)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def renew(self, request, pk=None):
        """تمدید قرارداد به‌عنوان یک SubscriptionOperation اتمیک."""
        subscription = self.get_object()
        new_end_date = request.data.get('new_end_date')
        notes = request.data.get('notes', '')
        if not new_end_date:
            return Response({'new_end_date': 'این فیلد الزامی است'}, status=status.HTTP_400_BAD_REQUEST)

        from datetime import date
        try:
            new_end_date = date.fromisoformat(new_end_date)
        except ValueError:
            return Response({'new_end_date': 'فرمت تاریخ نامعتبر است'}, status=status.HTTP_400_BAD_REQUEST)

        if new_end_date <= timezone.now().date() or new_end_date <= subscription.end_date:
            return Response(
                {'new_end_date': 'تاریخ پایان جدید باید بعد از تاریخ پایان فعلی و در آینده باشد'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            operation = SubscriptionOperation.objects.create(
                subscription=subscription,
                operation_type='renew',
                performed_by=request.user,
                old_start_date=subscription.start_date,
                new_start_date=subscription.start_date,
                old_end_date=subscription.end_date,
                new_end_date=new_end_date,
                old_status=subscription.status,
                new_status=subscription.status,
                notes=notes,
            )

            subscription.end_date = new_end_date
            subscription.save(update_fields=['end_date', 'updated_at'])

            # دستگاه‌های جدید
            for item in request.data.get('add_devices', []):
                device_id = item.get('device_id')
                if not device_id:
                    raise serializers.ValidationError({'add_devices': 'device_id الزامی است'})
                device_serializer = SubscriptionDeviceSerializer(
                    data={
                        'subscription': subscription.id,
                        'device': device_id,
                        'start_date': item.get('start_date', subscription.start_date),
                        'end_date': item.get('end_date', new_end_date),
                    }
                )
                device_serializer.is_valid(raise_exception=True)
                link = device_serializer.save()
                link.added_by_operation = operation
                link.save(update_fields=['added_by_operation'])

            # دستگاه‌های حذف‌شده
            for link_id in request.data.get('remove_device_ids', []):
                link = subscription.subscription_devices.filter(
                    id=link_id, unassigned_at__isnull=True
                ).first()
                if not link:
                    raise serializers.ValidationError(
                        {'remove_device_ids': f'دستگاه قرارداد با شناسه {link_id} یافت نشد'}
                    )
                link.unassigned_at = timezone.now()
                link.removed_by_operation = operation
                link.save(update_fields=['unassigned_at', 'removed_by_operation'])

            # پرداخت‌های مربوط به همین تمدید
            for item in request.data.get('payments', []):
                payment_serializer = SubscriptionPaymentSerializer(
                    data={**item, 'subscription': subscription.id, 'operation': operation.id}
                )
                payment_serializer.is_valid(raise_exception=True)
                payment_serializer.save()

            # تغییر اطلاعات مشتری
            customer_changes = request.data.get('customer_changes', {})
            if customer_changes:
                target = subscription.organization if subscription.customer_type == 'organization' else subscription.user
                if target is None:
                    raise serializers.ValidationError({'customer_changes': 'مشتری قرارداد یافت نشد'})

                allowed = {
                    'organization': {'name', 'code', 'registration_number', 'economy_code', 'phone', 'email', 'address', 'website'},
                    'personal': {'first_name', 'last_name', 'mobile', 'national_id', 'address'},
                }[subscription.customer_type]

                for field, new_value in customer_changes.items():
                    if field not in allowed or not hasattr(target, field):
                        raise serializers.ValidationError(
                            {'customer_changes': f'فیلد {field} قابل تغییر نیست'}
                        )
                    old_value = getattr(target, field)
                    if str(old_value) == str(new_value):
                        continue
                    SubscriptionOperationChange.objects.create(
                        operation=operation,
                        entity_type=target.__class__.__name__,
                        field_name=field,
                        old_value='' if old_value is None else str(old_value),
                        new_value='' if new_value is None else str(new_value),
                    )
                    setattr(target, field, new_value)
                target.save()

        return Response(SubscriptionSerializer(subscription).data)

    @action(detail=True, methods=['post'])
    def modify(self, request, pk=None):
        """ویرایش قرارداد به‌عنوان یک SubscriptionOperation اتمیک."""
        subscription = self.get_object()

        contract_changes = request.data.get('contract_changes', {})
        customer_changes = request.data.get('customer_changes', {})
        payment_changes = request.data.get('payment_changes', [])
        add_devices = request.data.get('add_devices', [])
        remove_device_ids = request.data.get('remove_device_ids', [])
        notes = request.data.get('notes', '')

        allowed_contract = {'start_date', 'end_date', 'notes'}
        if any(field not in allowed_contract for field in contract_changes):
            raise serializers.ValidationError({'contract_changes': 'فقط start_date، end_date و notes قابل ویرایش هستند'})

        from datetime import date
        parsed_contract = {}
        for field, value in contract_changes.items():
            if field in {'start_date', 'end_date'}:
                try:
                    parsed_contract[field] = date.fromisoformat(value) if value else None
                except (TypeError, ValueError):
                    raise serializers.ValidationError({field: 'فرمت تاریخ نامعتبر است'})
            else:
                parsed_contract[field] = value

        new_start = parsed_contract.get('start_date', subscription.start_date)
        new_end = parsed_contract.get('end_date', subscription.end_date)
        if new_start > new_end:
            raise serializers.ValidationError({'contract_changes': 'تاریخ شروع قرارداد باید قبل از تاریخ پایان باشد'})

        allowed_customer = {
            'organization': {'name', 'code', 'registration_number', 'economy_code', 'phone', 'email', 'address', 'website'},
            'personal': {'first_name', 'last_name', 'mobile', 'national_id', 'address'},
        }[subscription.customer_type]
        if any(field not in allowed_customer for field in customer_changes):
            raise serializers.ValidationError({'customer_changes': 'فیلد اطلاعات مشتری قابل ویرایش نیست'})

        payment_objects = {}
        for item in payment_changes:
            payment_id = item.get('id')
            if not payment_id:
                raise serializers.ValidationError({'payment_changes': 'شناسه پرداخت الزامی است'})
            payment = subscription.payments.filter(id=payment_id).first()
            if not payment:
                raise serializers.ValidationError({'payment_changes': f'پرداخت {payment_id} یافت نشد'})
            payment_objects[payment_id] = (payment, item)

        with transaction.atomic():
            operation = SubscriptionOperation.objects.create(
                subscription=subscription,
                operation_type='modify',
                performed_by=request.user,
                old_start_date=subscription.start_date,
                new_start_date=new_start,
                old_end_date=subscription.end_date,
                new_end_date=new_end,
                old_status=subscription.status,
                new_status=subscription.status,
                notes=notes,
            )

            # تغییرات قرارداد
            for field, new_value in parsed_contract.items():
                old_value = getattr(subscription, field)
                if str(old_value) != str(new_value):
                    SubscriptionOperationChange.objects.create(
                        operation=operation,
                        entity_type='Subscription',
                        field_name=field,
                        old_value='' if old_value is None else str(old_value),
                        new_value='' if new_value is None else str(new_value),
                    )
                    setattr(subscription, field, new_value)

            # اگر بازه قرارداد تغییر کرده، دستگاه‌های فعال باید همچنان داخل آن باشند.
            for link in subscription.subscription_devices.filter(unassigned_at__isnull=True):
                if link.start_date < new_start or link.end_date > new_end:
                    raise serializers.ValidationError({
                        'contract_changes': 'بازه جدید قرارداد با تاریخ یکی از دستگاه‌های فعال سازگار نیست'
                    })

            subscription.save()

            # دستگاه‌های جدید
            for item in add_devices:
                device_id = item.get('device_id')
                if not device_id:
                    raise serializers.ValidationError({'add_devices': 'device_id الزامی است'})
                device_serializer = SubscriptionDeviceSerializer(
                    data={
                        'subscription': subscription.id,
                        'device': device_id,
                        'start_date': item.get('start_date', new_start),
                        'end_date': item.get('end_date', new_end),
                    }
                )
                device_serializer.is_valid(raise_exception=True)
                link = device_serializer.save()
                link.added_by_operation = operation
                link.save(update_fields=['added_by_operation'])

            # دستگاه‌های حذف‌شده؛ رکورد تاریخی حفظ می‌شود.
            for link_id in remove_device_ids:
                link = subscription.subscription_devices.filter(
                    id=link_id, unassigned_at__isnull=True
                ).first()
                if not link:
                    raise serializers.ValidationError(
                        {'remove_device_ids': f'دستگاه قرارداد با شناسه {link_id} یافت نشد'}
                    )
                link.unassigned_at = timezone.now()
                link.removed_by_operation = operation
                link.save(update_fields=['unassigned_at', 'removed_by_operation'])

            # تغییر اطلاعات مشتری
            if customer_changes:
                target = subscription.organization if subscription.customer_type == 'organization' else subscription.user
                if target is None:
                    raise serializers.ValidationError({'customer_changes': 'مشتری قرارداد یافت نشد'})
                for field, new_value in customer_changes.items():
                    old_value = getattr(target, field)
                    if str(old_value) == str(new_value):
                        continue
                    SubscriptionOperationChange.objects.create(
                        operation=operation,
                        entity_type=target.__class__.__name__,
                        field_name=field,
                        old_value='' if old_value is None else str(old_value),
                        new_value='' if new_value is None else str(new_value),
                    )
                    setattr(target, field, new_value)
                target.save()

            # اصلاح پرداخت‌ها؛ هر اصلاح هم در همان عملیات ثبت می‌شود.
            payment_fields = {'amount', 'payment_date', 'device_count', 'description'}
            for payment, item in payment_objects.values():
                for field in payment_fields:
                    if field not in item:
                        continue
                    new_value = item[field]
                    if field == 'amount':
                        new_value = int(new_value)
                    elif field == 'device_count':
                        new_value = int(new_value)
                    elif field == 'payment_date':
                        try:
                            new_value = date.fromisoformat(new_value)
                        except (TypeError, ValueError):
                            raise serializers.ValidationError({'payment_changes': 'فرمت تاریخ پرداخت نامعتبر است'})
                    old_value = getattr(payment, field)
                    if str(old_value) == str(new_value):
                        continue
                    SubscriptionOperationChange.objects.create(
                        operation=operation,
                        entity_type='SubscriptionPayment',
                        field_name=field,
                        old_value='' if old_value is None else str(old_value),
                        new_value='' if new_value is None else str(new_value),
                    )
                    setattr(payment, field, new_value)
                payment.save()

        return Response(SubscriptionSerializer(subscription).data)

    @action(detail=True, methods=['get'])
    def operations(self, request, pk=None):
        subscription = self.get_object()
        qs = subscription.operations.select_related('performed_by').prefetch_related('changes')
        return Response(SubscriptionOperationSerializer(qs, many=True).data)

    

    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        """تعلیق قرارداد"""
        subscription = self.get_object()
        with transaction.atomic():
            operation = SubscriptionOperation.objects.create(
                subscription=subscription, operation_type='suspend',
                performed_by=request.user, old_status=subscription.status, new_status='suspended'
            )
            subscription.status = 'suspended'
            subscription.save(update_fields=['status', 'updated_at'])
        return Response(SubscriptionSerializer(subscription).data)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """فعال‌سازی مجدد قرارداد"""
        subscription = self.get_object()
        with transaction.atomic():
            operation = SubscriptionOperation.objects.create(
                subscription=subscription, operation_type='activate',
                performed_by=request.user, old_status=subscription.status, new_status='active'
            )
            subscription.status = 'active'
            subscription.save(update_fields=['status', 'updated_at'])
        return Response(SubscriptionSerializer(subscription).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """لغو قرارداد"""
        subscription = self.get_object()
        with transaction.atomic():
            operation = SubscriptionOperation.objects.create(
                subscription=subscription, operation_type='cancel',
                performed_by=request.user, old_status=subscription.status, new_status='cancelled'
            )
            subscription.status = 'cancelled'
            subscription.save(update_fields=['status', 'updated_at'])
        return Response(SubscriptionSerializer(subscription).data)

    @action(detail=False, methods=['get'])
    def next_number(self, request):
        """
        تولید شماره قرارداد بعدی
        GET /api/subscriptions/next_number/?type=organization
        """
        customer_type = request.query_params.get('type', 'organization')
        if customer_type not in ['organization', 'personal']:
            customer_type = 'organization'
        
        number = Subscription.generate_contract_number(customer_type)
        return Response({'contract_number': number})

    def destroy(self, request, *args, **kwargs):
        """حذف فیزیکی نمی‌کنیم — فقط status رو cancelled می‌کنیم"""
        subscription = self.get_object()

        # اگه قبلاً cancelled شده، اجازه بده
        if subscription.status == 'cancelled':
            return Response(status=status.HTTP_204_NO_CONTENT)

        subscription.status = 'cancelled'
        subscription.save()

        # همه‌ی دستگاه‌ها رو از قرارداد خارج کن
        from django.utils import timezone
        active_links = subscription.subscription_devices.filter(unassigned_at__isnull=True)
        for link in active_links:
            link.unassigned_at = timezone.now()
            link.save()

            # برگرداندن دستگاه به انبار
            device = link.device
            other_active = device.subscription_links.filter(
                unassigned_at__isnull=True
            ).exclude(id=link.id).exists()
            if not other_active:
                device.organization = None
                device.owner_user = None
                device.branch = None
                device.management_status = 'warehouse'
                device.save()

        return Response(status=status.HTTP_204_NO_CONTENT)

    
# ═══════════════════════════════════════════════
# SubscriptionDevice
# ═══════════════════════════════════════════════

class SubscriptionDeviceViewSet(viewsets.ModelViewSet):
    queryset = SubscriptionDevice.objects.select_related(
        'subscription', 'device'
    ).all()
    serializer_class = SubscriptionDeviceSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        return context

    
    def get_queryset(self):
        user = self.request.user
        qs = SubscriptionDevice.objects.select_related('subscription', 'device')

        if user.is_site_admin:
            pass
        elif user.organization_id:
            qs = qs.filter(subscription__organization_id=user.organization_id)
        elif user.is_personal_user:
            qs = qs.filter(subscription__user=user)
        else:
            qs = qs.none()

        subscription = self.request.query_params.get('subscription')
        if subscription:
            qs = qs.filter(subscription_id=subscription)

        active_only = self.request.query_params.get('active')
        if active_only == 'true':
            qs = qs.filter(unassigned_at__isnull=True)

        return qs

    def get_permissions(self):
        if self.action in ['create', 'destroy', 'update', 'partial_update']:
            return [IsSiteAdmin()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription = serializer.validated_data['subscription']
        with transaction.atomic():
            operation = SubscriptionOperation.objects.create(
                subscription=subscription,
                operation_type='add_device',
                performed_by=request.user,
                old_end_date=subscription.end_date,
                new_end_date=subscription.end_date,
            )
            instance = serializer.save(added_by_operation=operation)
        return Response(self.get_serializer(instance).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        """خروج دستگاه از قرارداد به‌عنوان یک عملیات حسابرسی‌شده."""
        instance = self.get_object()
        subscription = instance.subscription
        with transaction.atomic():
            operation = SubscriptionOperation.objects.create(
                subscription=subscription,
                operation_type='remove_device',
                performed_by=request.user,
                old_end_date=subscription.end_date,
                new_end_date=subscription.end_date,
            )
            instance.unassigned_at = timezone.now()
            instance.removed_by_operation = operation
            instance.save(update_fields=['unassigned_at', 'removed_by_operation'])

            device = instance.device
            other_active = device.subscription_links.filter(
                unassigned_at__isnull=True
            ).exclude(id=instance.id).exists()
            if not other_active:
                device.organization = None
                device.owner_user = None
                device.branch = None
                device.management_status = 'warehouse'
                device.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
# ═══════════════════════════════════════════════
# SubscriptionPayment
# ═══════════════════════════════════════════════

class SubscriptionPaymentViewSet(viewsets.ModelViewSet):
    queryset = SubscriptionPayment.objects.select_related('subscription').all()
    serializer_class = SubscriptionPaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = SubscriptionPayment.objects.select_related('subscription')

        if user.is_site_admin:
            pass
        elif user.organization_id:
            qs = qs.filter(subscription__organization_id=user.organization_id)
        elif user.is_personal_user:
            qs = qs.filter(subscription__user=user)
        else:
            qs = qs.none()

        subscription = self.request.query_params.get('subscription')
        if subscription:
            qs = qs.filter(subscription_id=subscription)

        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription = serializer.validated_data['subscription']
        with transaction.atomic():
            operation = SubscriptionOperation.objects.create(
                subscription=subscription,
                operation_type='payment',
                performed_by=request.user,
                old_end_date=subscription.end_date,
                new_end_date=subscription.end_date,
            )
            instance = serializer.save(operation=operation)
        return Response(self.get_serializer(instance).data, status=status.HTTP_201_CREATED)

    def get_permissions(self):
        if self.action in ['create', 'destroy', 'update', 'partial_update']:
            return [IsSiteAdmin()]
        return super().get_permissions()