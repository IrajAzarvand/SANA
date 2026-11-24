from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from datetime import timedelta
from rest_framework import viewsets, filters, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    Organization,
    Branch,
    Subscription,
    SubscriptionDevice,
    SubscriptionPayment,
    SubscriptionPaymentAllocation,
    SubscriptionOperation,
    SubscriptionOperationChange,
)
from .serializers import (
    OrganizationSerializer,
    OrganizationSettingsSerializer,
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
from accounts.permissions import IsSiteAdmin, IsMainUserOrSiteAdmin
from fleet.models import Device, DeviceCustomerAccessPeriod
from fleet.lifecycle import record_device_lifecycle_event
from fleet.device_operations import _close_branch_history, _close_customer_access, _open_customer_access


# ═══════════════════════════════════════════════
# Organization
# ═══════════════════════════════════════════════

class CanManageOrganizationSettings(BasePermission):
    """Only site admins and organization owners can edit organization details."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated
            and (user.is_site_admin or user.is_main_user)
        )


class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'registration_number']
    ordering_fields = ['name', 'created_at']

    def get_serializer_class(self):
        if (
            self.action in ['update', 'partial_update']
            and not self.request.user.is_site_admin
        ):
            return OrganizationSettingsSerializer
        if self.action == 'list':
            return OrganizationListSerializer
        return OrganizationSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_site_admin:
            return Organization.objects.all()
        if user.is_branch_manager:
            return Organization.objects.none()
        if user.organization_id:
            return Organization.objects.filter(id=user.organization_id).exclude(status='archived')
        return Organization.objects.none()

    def get_permissions(self):
        if self.action in ['create', 'destroy', 'restore', 'archive']:
            return [IsSiteAdmin()]
        if self.action in ['update', 'partial_update']:
            return [CanManageOrganizationSettings()]
        return super().get_permissions()

    def perform_destroy(self, instance):
        # Organization deletion is archival: financial and operational history must survive.
        if instance.status == 'archived':
            return
        instance.archived_from_status = instance.status
        instance.status = 'archived'
        instance.archived_at = timezone.now()
        instance.archived_by = self.request.user
        instance.save(update_fields=['status', 'archived_at', 'archived_by', 'archived_from_status', 'updated_at'])

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        organization = self.get_object()
        self.perform_destroy(organization)
        return Response(self.get_serializer(organization).data)

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        organization = self.get_object()
        if organization.status != 'archived':
            return Response(
                {'detail': 'این شرکت در وضعیت بایگانی نیست.'},
                status=status.HTTP_409_CONFLICT,
            )
        organization.status = organization.archived_from_status if organization.archived_from_status in {'active', 'inactive', 'suspended'} else 'active'
        organization.archived_at = None
        organization.archived_by = None
        organization.archived_from_status = ''
        organization.save(update_fields=['status', 'archived_at', 'archived_by', 'archived_from_status', 'updated_at'])
        return Response(self.get_serializer(organization).data)


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

        if not user.is_site_admin:
            qs = qs.exclude(organization__status='archived')

        org = self.request.query_params.get('organization')
        if org:
            qs = qs.filter(organization_id=org)

        return qs

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsSiteAdmin()]
        if self.action in ['create', 'update', 'partial_update']:
            return [IsMainUserOrSiteAdmin()]
        return super().get_permissions()

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_main_user and user.organization and user.organization.status == 'archived':
            raise serializers.ValidationError('شرکت بایگانی شده و امکان ایجاد یا تغییر شعبه ندارد.')
        if user.is_main_user:
            if not user.organization_id:
                raise serializers.ValidationError('حساب مدیر شرکت به سازمان معتبری متصل نیست.')
            serializer.save(organization=user.organization)
            return
        serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        if user.is_main_user:
            # Never allow a company manager to move a branch into another tenant.
            serializer.save(organization=user.organization)
            return
        serializer.save()


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
        elif user.is_branch_manager:
            qs = qs.none()
        elif user.is_main_user and user.organization_id:
            qs = qs.filter(organization_id=user.organization_id)
        elif user.is_personal_user:
            qs = qs.filter(user=user)
        else:
            qs = qs.none()

        if not user.is_site_admin:
            qs = qs.exclude(organization__status='archived')

        # فیلترها
        status_filter = self.request.query_params.get('status')
        if status_filter:
            today = timezone.localdate()
            if status_filter == 'active':
                qs = qs.filter(
                    status='active',
                    start_date__lte=today,
                    end_date__gte=today,
                )
            elif status_filter == 'pending':
                qs = qs.filter(status='active', start_date__gt=today)
            elif status_filter == 'expired':
                from django.db.models import Q
                qs = qs.filter(
                    Q(status='expired')
                    | Q(status='active', end_date__lt=today)
                )
            else:
                qs = qs.filter(status=status_filter)

        customer_type = self.request.query_params.get('customer_type')
        if customer_type:
            qs = qs.filter(customer_type=customer_type)

        organization_filter = self.request.query_params.get('organization')
        if organization_filter:
            qs = qs.filter(organization_id=organization_filter)

        expiring = self.request.query_params.get('expiring')
        if expiring == 'true':
            today = timezone.now().date()
            thirty_days = today + timedelta(days=30)
            qs = qs.filter(
                status='active',
                start_date__lte=today,
                end_date__gte=today,
                end_date__lte=thirty_days,
            )

        return qs

    def get_permissions(self):
        if self.action in ['create', 'destroy', 'update', 'partial_update', 'renew', 'modify', 'revise_installment_plan', 'suspend', 'activate', 'cancel']:
            return [IsSiteAdmin()]
        return super().get_permissions()

    def update(self, request, *args, **kwargs):
        return Response(
            {'detail': 'ویرایش مستقیم قرارداد غیرفعال است؛ از مسیر ثبت عملیات ویرایش استفاده کنید.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {'detail': 'حذف قرارداد غیرفعال است؛ برای خاتمه قرارداد از عملیات لغو استفاده کنید.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

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
        from .financial import allocate_payment
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
            from datetime import datetime, time, timedelta
            from fleet.models import Device, DeviceCustomerAccessPeriod
            from fleet.device_operations import _open_branch_history

            subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)
            today = timezone.localdate()
            if subscription.status == 'cancelled':
                raise serializers.ValidationError({'detail': 'قرارداد لغوشده قابل تمدید نیست.'})
            if new_end_date <= today or new_end_date <= subscription.end_date:
                raise serializers.ValidationError({
                    'new_end_date': 'تاریخ پایان جدید باید بعد از تاریخ پایان فعلی و در آینده باشد'
                })

            old_status = subscription.status
            old_end_date = subscription.end_date
            expired_by_date = old_end_date < today
            explicitly_expired = old_status == 'expired'
            split_device_links = expired_by_date or explicitly_expired
            renewal_time = timezone.now()
            if expired_by_date:
                expiration_cutoff = timezone.make_aware(
                    datetime.combine(old_end_date + timedelta(days=1), time.min),
                    timezone.get_current_timezone(),
                )
            else:
                expiration_cutoff = renewal_time

            new_status = 'active' if explicitly_expired else old_status
            operation = SubscriptionOperation.objects.create(
                subscription=subscription,
                operation_type='renew',
                performed_by=request.user,
                old_start_date=subscription.start_date,
                new_start_date=subscription.start_date,
                old_end_date=old_end_date,
                new_end_date=new_end_date,
                old_status=old_status,
                new_status=new_status,
                notes=notes,
            )

            if split_device_links:
                # An expired interval is a real access gap. Preserve the old
                # link for historical scope and create a fresh link at renewal
                # time so personal-customer history cannot include the gap.
                remove_link_ids = {str(value) for value in request.data.get('remove_device_ids', [])}
                processed_remove_ids = set()
                active_links = list(
                    subscription.subscription_devices.filter(
                        unassigned_at__isnull=True
                    ).select_related('device').order_by('device_id', 'id')
                )

                subscription.end_date = new_end_date
                subscription.status = new_status
                subscription.save(update_fields=['end_date', 'status', 'updated_at'])

                for old_link in active_links:
                    device = Device.objects.select_for_update().get(pk=old_link.device_id)
                    unassigned_at = max(expiration_cutoff, old_link.assigned_at)
                    SubscriptionDevice.objects.filter(pk=old_link.pk).update(
                        unassigned_at=unassigned_at,
                        removed_by_operation=operation,
                    )
                    old_link.unassigned_at = unassigned_at
                    old_link.removed_by_operation = operation

                    open_periods = DeviceCustomerAccessPeriod.objects.filter(
                        device=device,
                        subscription=subscription,
                        ended_at__isnull=True,
                    )
                    for period in open_periods:
                        period.ended_at = max(expiration_cutoff, period.started_at)
                        period.reason = 'contract_expired'
                        period.save(update_fields=['ended_at', 'reason'])

                    if str(old_link.id) in remove_link_ids:
                        _close_branch_history(device, when=renewal_time)
                        record_device_lifecycle_event(
                            device=device,
                            event_type='removed_from_contract',
                            performed_by=request.user,
                            subscription=subscription,
                            organization=subscription.organization,
                            user=subscription.user,
                            description=f'دستگاه از قرارداد {subscription.contract_number} خارج شد؛ مالکیت دستگاه حفظ شد.',
                        )
                        processed_remove_ids.add(str(old_link.id))
                        continue

                    new_start_date = max(old_link.start_date, today)
                    new_link = SubscriptionDevice.objects.create(
                        subscription=subscription,
                        device=device,
                        start_date=new_start_date,
                        end_date=new_end_date,
                        added_by_operation=operation,
                    )
                    if device.management_status in {'installed', 'active', 'disconnected'}:
                        _open_branch_history(
                            device,
                            device.branch,
                            subscription=subscription,
                            reason='contract_renewal_after_expiration',
                        )
                    else:
                        _close_branch_history(device)
                    _open_customer_access(
                        device,
                        subscription=subscription,
                        branch=device.branch,
                        organization=subscription.organization,
                        user=subscription.user,
                        started_at=renewal_time,
                        reason='contract_renewal_after_expiration',
                    )
            else:
                # Continuous renewal keeps the existing assignment/access period.
                subscription.subscription_devices.filter(
                    unassigned_at__isnull=True
                ).update(end_date=new_end_date)
                subscription.end_date = new_end_date
                subscription.status = new_status
                subscription.save(update_fields=['end_date', 'status', 'updated_at'])
                processed_remove_ids = set()

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
                if str(link_id) in processed_remove_ids:
                    continue
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
                _close_customer_access(link.device, subscription=subscription)
                _close_branch_history(link.device)
                record_device_lifecycle_event(
                    device=link.device,
                    event_type='removed_from_contract',
                    performed_by=request.user,
                    subscription=subscription,
                    organization=subscription.organization,
                    user=subscription.user,
                    description=f'دستگاه از قرارداد {subscription.contract_number} خارج شد؛ مالکیت دستگاه حفظ شد.',
                )

            # پرداخت‌های مربوط به همین تمدید
            for item in request.data.get('payments', []):
                payment_serializer = SubscriptionPaymentSerializer(
                    data={**item, 'subscription': subscription.id, 'operation': operation.id}
                )
                payment_serializer.is_valid(raise_exception=True)
                payment = payment_serializer.save()
                allocate_payment(payment)

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

        subscription.refresh_from_db()
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
            raise serializers.ValidationError({'contract_changes': 'فقط start_date، end_date و notes قابل ارسال هستند'})

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

        for field in ('start_date', 'end_date'):
            if field in parsed_contract and parsed_contract[field] != getattr(subscription, field):
                raise serializers.ValidationError({
                    field: 'تاریخ‌های قرارداد فقط از مسیر تمدید یا فعال‌سازی مجدد قابل تغییر هستند.'
                })

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
            locked_subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)
            if (
                new_start != locked_subscription.start_date
                or new_end != locked_subscription.end_date
            ):
                raise serializers.ValidationError({
                    'contract_changes': 'قرارداد هم‌زمان تغییر کرده است؛ اطلاعات را تازه‌سازی و دوباره تلاش کنید.'
                })
            subscription = locked_subscription
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
                _close_customer_access(link.device, subscription=subscription)
                _close_branch_history(link.device)
                record_device_lifecycle_event(
                    device=link.device,
                    event_type='removed_from_contract',
                    performed_by=request.user,
                    subscription=subscription,
                    organization=subscription.organization,
                    user=subscription.user,
                    description=f'دستگاه از قرارداد {subscription.contract_number} خارج شد؛ مالکیت دستگاه حفظ شد.',
                )

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

            # دریافتی‌ای که تخصیص مالی دارد قابل ویرایش مستقیم نیست؛
            # برای اصلاح آن باید در جریان مالی جداگانه برگشت/اصلاح ثبت شود.
            payment_fields = {'amount', 'payment_date', 'description'}
            for payment, item in payment_objects.values():
                if payment.allocations.exists():
                    raise serializers.ValidationError({
                        'payment_changes': f'دریافتی {payment.id} تخصیص مالی دارد و قابل ویرایش مستقیم نیست'
                    })
                for field in payment_fields:
                    if field not in item:
                        continue
                    new_value = item[field]
                    if field == 'amount':
                        new_value = int(new_value)
                    model_field = field
                    if field == 'payment_date':
                        try:
                            new_value = date.fromisoformat(new_value)
                        except (TypeError, ValueError):
                            raise serializers.ValidationError({'payment_changes': 'فرمت تاریخ دریافت وجه نامعتبر است'})
                        model_field = 'received_at'
                    old_value = getattr(payment, model_field)
                    if str(old_value) == str(new_value):
                        continue
                    SubscriptionOperationChange.objects.create(
                        operation=operation,
                        entity_type='SubscriptionPayment',
                        field_name=model_field,
                        old_value='' if old_value is None else str(old_value),
                        new_value='' if new_value is None else str(new_value),
                    )
                    setattr(payment, model_field, new_value)
                payment.save()

        return Response(SubscriptionSerializer(subscription).data)

    @action(detail=True, methods=['post'])
    def revise_installment_plan(self, request, pk=None):
        """Revise only the unpaid remainder; old schedule versions stay intact."""
        from .financial import revise_installment_plan

        subscription = self.get_object()
        with transaction.atomic():
            operation = SubscriptionOperation.objects.create(
                subscription=subscription,
                operation_type='modify',
                performed_by=request.user,
                old_start_date=subscription.start_date,
                new_start_date=subscription.start_date,
                old_end_date=subscription.end_date,
                new_end_date=subscription.end_date,
                old_status=subscription.status,
                new_status=subscription.status,
                notes='بازتنظیم برنامه اقساط؛ اقساط پرداخت‌شده و تخصیص‌های قبلی حفظ شدند.',
            )
            old_price = subscription.price
            revise_installment_plan(
                subscription,
                request.data,
                created_by=request.user,
            )
            subscription.refresh_from_db()
            if old_price != subscription.price:
                SubscriptionOperationChange.objects.create(
                    operation=operation,
                    entity_type='Subscription',
                    field_name='price',
                    old_value=str(old_price),
                    new_value=str(subscription.price),
                )
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
            subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)
            operation = SubscriptionOperation.objects.create(
                subscription=subscription, operation_type='suspend',
                performed_by=request.user, old_status=subscription.status, new_status='suspended'
            )
            subscription.status = 'suspended'
            subscription.save(update_fields=['status', 'updated_at'])
            # Close scheduled/current live periods without changing the physical
            # branch assignment; historical access remains available.
            active_links = subscription.subscription_devices.filter(
                unassigned_at__isnull=True
            ).select_related('device')
            for link in active_links:
                _close_customer_access(link.device, subscription=subscription)
        return Response(SubscriptionSerializer(subscription).data)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """فعال‌سازی مجدد قرارداد"""
        subscription = self.get_object()
        with transaction.atomic():
            from datetime import date, datetime, time, timedelta
            from fleet.models import Device, DeviceCustomerAccessPeriod
            from fleet.device_operations import _open_branch_history

            subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)
            today = timezone.localdate()
            if subscription.status == 'cancelled':
                raise serializers.ValidationError({'status': 'قرارداد لغوشده قابل فعال‌سازی مجدد نیست.'})
            if subscription.status == 'active' and subscription.end_date >= today:
                raise serializers.ValidationError({'status': 'قرارداد در حال حاضر فعال است.'})

            raw_end_date = request.data.get('end_date')
            if raw_end_date:
                try:
                    new_end_date = date.fromisoformat(raw_end_date)
                except (TypeError, ValueError):
                    raise serializers.ValidationError({'end_date': 'تاریخ پایان جدید معتبر نیست.'})
            else:
                new_end_date = subscription.end_date
            if new_end_date < today or new_end_date < subscription.start_date:
                raise serializers.ValidationError({'end_date': 'تاریخ پایان باید امروز یا بعد از آن و پس از شروع قرارداد باشد.'})

            old_status = subscription.status
            old_end_date = subscription.end_date
            split_device_links = old_end_date < today or old_status == 'expired'
            activation_time = timezone.now()
            if old_end_date < today:
                expiration_cutoff = timezone.make_aware(
                    datetime.combine(old_end_date + timedelta(days=1), time.min),
                    timezone.get_current_timezone(),
                )
            else:
                expiration_cutoff = activation_time

            operation = SubscriptionOperation.objects.create(
                subscription=subscription,
                operation_type='activate',
                performed_by=request.user,
                old_status=old_status,
                new_status='active',
                old_end_date=old_end_date,
                new_end_date=new_end_date,
            )
            subscription.status = 'active'
            subscription.end_date = new_end_date
            subscription.save(update_fields=['status', 'end_date', 'updated_at'])

            active_links = list(
                subscription.subscription_devices.filter(
                    unassigned_at__isnull=True
                ).select_related('device').order_by('device_id', 'id')
            )
            for old_link in active_links:
                device = Device.objects.select_for_update().get(pk=old_link.device_id)
                conflicting_period = DeviceCustomerAccessPeriod.objects.filter(
                    device=device,
                    ended_at__isnull=True,
                ).exclude(subscription=subscription).first()
                if conflicting_period:
                    raise serializers.ValidationError({
                        'device': 'برای یکی از دستگاه‌های قرارداد، دوره دسترسی باز متعلق به قرارداد دیگری وجود دارد.'
                    })

                if split_device_links:
                    # Preserve the expired gap in both organization and personal
                    # history scopes: end the old link at expiry, then start a
                    # new assignment at this activation.
                    unassigned_at = max(expiration_cutoff, old_link.assigned_at)
                    SubscriptionDevice.objects.filter(pk=old_link.pk).update(
                        unassigned_at=unassigned_at,
                        removed_by_operation=operation,
                    )
                    open_periods = DeviceCustomerAccessPeriod.objects.filter(
                        device=device,
                        subscription=subscription,
                        ended_at__isnull=True,
                    )
                    for period in open_periods:
                        period.ended_at = max(expiration_cutoff, period.started_at)
                        period.reason = 'contract_expired'
                        period.save(update_fields=['ended_at', 'reason'])

                    new_link = SubscriptionDevice.objects.create(
                        subscription=subscription,
                        device=device,
                        start_date=max(old_link.start_date, today),
                        end_date=new_end_date,
                        added_by_operation=operation,
                    )
                else:
                    old_link.end_date = new_end_date
                    old_link.save(update_fields=['end_date'])
                    _close_customer_access(device, activation_time, subscription=subscription)

                if device.management_status in {'installed', 'active', 'disconnected'}:
                    _open_branch_history(
                        device,
                        device.branch,
                        subscription=subscription,
                        reason='contract_reactivation',
                    )
                else:
                    _close_branch_history(device)

                customer_kwargs = (
                    {'organization': subscription.organization, 'user': None}
                    if subscription.customer_type == 'organization'
                    else {'organization': None, 'user': subscription.user}
                )
                _open_customer_access(
                    device,
                    subscription=subscription,
                    branch=device.branch if subscription.customer_type == 'organization' else None,
                    started_at=activation_time,
                    reason='فعال‌سازی مجدد قرارداد',
                    **customer_kwargs,
                )

        subscription.refresh_from_db()
        return Response(SubscriptionSerializer(subscription).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """لغو قرارداد و پایان‌دادن به تخصیص دستگاه‌های فعال آن."""
        subscription = self.get_object()
        with transaction.atomic():
            subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)
            operation = SubscriptionOperation.objects.create(
                subscription=subscription, operation_type='cancel',
                performed_by=request.user, old_status=subscription.status, new_status='cancelled'
            )
            subscription.status = 'cancelled'
            subscription.save(update_fields=['status', 'updated_at'])

            active_links = SubscriptionDevice.objects.select_related('device').filter(
                subscription=subscription,
                unassigned_at__isnull=True,
            )
            unassigned_at = timezone.now()
            for link in active_links:
                link.unassigned_at = unassigned_at
                link.removed_by_operation = operation
                link.save(update_fields=['unassigned_at', 'removed_by_operation'])
                _close_customer_access(link.device, subscription=subscription)
                _close_branch_history(link.device)
                record_device_lifecycle_event(
                    device=link.device,
                    event_type='removed_from_contract',
                    performed_by=request.user,
                    subscription=subscription,
                    organization=subscription.organization,
                    user=subscription.user,
                    description=f'دستگاه به‌دلیل لغو قرارداد {subscription.contract_number} از قرارداد خارج شد؛ مالکیت دستگاه حفظ شد.',
                )
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
        return Response(
            {'detail': 'حذف مستقیم قرارداد غیرفعال است؛ برای خاتمه قرارداد از عملیات لغو استفاده کنید.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    
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
        elif user.is_branch_manager:
            qs = qs.none()
        elif user.is_main_user and user.organization_id:
            qs = qs.filter(subscription__organization_id=user.organization_id)
        elif user.is_personal_user:
            qs = qs.filter(subscription__user=user)
        else:
            qs = qs.none()

        if not user.is_site_admin:
            qs = qs.exclude(subscription__organization__status='archived')

        subscription = self.request.query_params.get('subscription')
        if subscription:
            qs = qs.filter(subscription_id=subscription)

        active_only = self.request.query_params.get('active')
        if active_only == 'true':
            qs = qs.filter(unassigned_at__isnull=True)

        return qs

    def get_permissions(self):
        if self.action in ['create', 'destroy', 'update', 'partial_update', 'allocate']:
            return [IsSiteAdmin()]
        return super().get_permissions()

    def update(self, request, *args, **kwargs):
        return Response(
            {'detail': 'ویرایش مستقیم ارتباط دستگاه با قرارداد غیرفعال است؛ از عملیات ویرایش قرارداد استفاده کنید.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

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
        """خروج دستگاه از قرارداد؛ مالکیت دستگاه حفظ می‌شود."""
        instance = self.get_object()
        subscription = instance.subscription
        with transaction.atomic():
            subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)
            device = Device.objects.select_for_update().get(pk=instance.device_id)
            instance = SubscriptionDevice.objects.select_for_update().get(
                pk=instance.pk,
                subscription=subscription,
                device=device,
            )
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
            _close_customer_access(instance.device, subscription=subscription)
            _close_branch_history(instance.device)

            record_device_lifecycle_event(
                device=instance.device,
                event_type='removed_from_contract',
                performed_by=request.user,
                subscription=subscription,
                organization=subscription.organization,
                user=subscription.user,
                description=f'دستگاه از قرارداد {subscription.contract_number} خارج شد؛ مالکیت دستگاه حفظ شد.',
            )
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
        elif user.is_branch_manager:
            qs = qs.none()
        elif user.is_main_user and user.organization_id:
            qs = qs.filter(subscription__organization_id=user.organization_id)
        elif user.is_personal_user:
            qs = qs.filter(subscription__user=user)
        else:
            qs = qs.none()

        if not user.is_site_admin:
            qs = qs.exclude(subscription__organization__status='archived')

        subscription = self.request.query_params.get('subscription')
        if subscription:
            qs = qs.filter(subscription_id=subscription)

        return qs

    def create(self, request, *args, **kwargs):
        from .financial import allocate_payment

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription = serializer.validated_data['subscription']
        allocation_mode = request.data.get('allocation_mode', 'automatic')
        allocations = request.data.get('allocations')
        with transaction.atomic():
            operation = SubscriptionOperation.objects.create(
                subscription=subscription,
                operation_type='payment',
                performed_by=request.user,
                old_end_date=subscription.end_date,
                new_end_date=subscription.end_date,
            )
            instance = serializer.save(operation=operation)
            if allocation_mode == 'contract_advance':
                from decimal import Decimal
                from django.db.models import Sum
                received_before = subscription.payments.exclude(pk=instance.pk).aggregate(
                    total=Sum('amount')
                )['total'] or Decimal('0')
                contract_balance_before = max(Decimal(subscription.price) - received_before, Decimal('0'))
                allocate_payment(
                    instance,
                    allocation_type='contract_advance',
                    allocation_amount=min(Decimal(instance.amount), contract_balance_before),
                )
            elif allocation_mode == 'credit':
                # Deliberately leave the receipt unallocated as customer credit.
                pass
            else:
                allocate_payment(
                    instance,
                    mode=allocation_mode,
                    allocations=allocations,
                )
        return Response(self.get_serializer(instance).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def allocate(self, request, pk=None):
        """Apply an existing unallocated receipt to selected or oldest unpaid installments."""
        from .financial import allocate_payment

        payment = self.get_object()
        allocation_mode = request.data.get('allocation_mode', 'automatic')
        allocations = request.data.get('allocations')
        with transaction.atomic():
            SubscriptionOperation.objects.create(
                subscription=payment.subscription,
                operation_type='payment',
                performed_by=request.user,
                old_end_date=payment.subscription.end_date,
                new_end_date=payment.subscription.end_date,
                notes=f'تخصیص مجدد دریافتی شماره {payment.id}',
            )
            allocate_payment(
                payment,
                mode=allocation_mode,
                allocations=allocations,
            )
        payment.refresh_from_db()
        return Response(self.get_serializer(payment).data)

    def update(self, request, *args, **kwargs):
        return Response(
            {'detail': 'ویرایش مستقیم دریافتی غیرفعال است؛ از عملیات اصلاح قرارداد استفاده کنید.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {'detail': 'حذف مستقیم دریافتی غیرفعال است تا سابقه مالی حفظ شود.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def get_permissions(self):
        if self.action in ['create', 'destroy', 'update', 'partial_update', 'allocate']:
            return [IsSiteAdmin()]
        return super().get_permissions()