from django.utils import timezone
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
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
    SubscriptionOrganizationCustomerChangeSerializer,
    SubscriptionPersonalCustomerChangeSerializer,
)
from accounts.permissions import IsSiteAdmin, IsMainUserOrSiteAdmin
from fleet.lifecycle import record_device_lifecycle_event
from fleet.models import Device
from fleet.device_operations import _close_customer_access
from fleet.customer_access import active_customer_access_periods, active_personal_contract_links, active_subscription_links


def _lock_subscription_devices(subscription, add_devices=None):
    """Lock device rows in stable order before locking their parent contract."""
    device_ids = set(
        subscription.subscription_devices.filter(
            unassigned_at__isnull=True
        ).values_list('device_id', flat=True)
    )
    if add_devices is None:
        add_devices = []
    if not isinstance(add_devices, list):
        raise serializers.ValidationError({
            'add_devices': 'فهرست دستگاه‌های جدید باید آرایه باشد.'
        })
    for item in add_devices:
        if not isinstance(item, dict):
            raise serializers.ValidationError({
                'add_devices': 'هر دستگاه باید به‌صورت یک شیء معتبر ارسال شود.'
            })
        device_id = item.get('device_id')
        if isinstance(device_id, bool) or device_id in (None, ''):
            raise serializers.ValidationError({
                'add_devices': 'شناسه دستگاه الزامی و باید عدد صحیح مثبت باشد.'
            })
        if not (
            (isinstance(device_id, int) and not isinstance(device_id, bool))
            or (isinstance(device_id, str) and device_id.isdecimal())
        ):
            raise serializers.ValidationError({
                'add_devices': 'شناسه دستگاه نامعتبر است.'
            })
        normalized_device_id = int(device_id)
        if normalized_device_id <= 0:
            raise serializers.ValidationError({
                'add_devices': 'شناسه دستگاه باید عدد صحیح مثبت باشد.'
            })
        device_ids.add(normalized_device_id)
    if device_ids:
        list(
            Device.objects.select_for_update()
            .filter(pk__in=device_ids)
            .order_by('pk')
            .values_list('pk', flat=True)
        )



def _validated_positive_id_list(value, field_name):
    if value is None:
        return []
    if not isinstance(value, list):
        raise serializers.ValidationError({
            field_name: 'مقدار باید فهرستی از شناسه‌های معتبر باشد.'
        })
    normalized = []
    for raw_id in value:
        if isinstance(raw_id, bool):
            raise serializers.ValidationError({field_name: 'شناسه نامعتبر است.'})
        if not (
            (isinstance(raw_id, int) and not isinstance(raw_id, bool))
            or (isinstance(raw_id, str) and raw_id.isdecimal())
        ):
            raise serializers.ValidationError({field_name: 'شناسه نامعتبر است.'})
        item_id = int(raw_id)
        if item_id <= 0:
            raise serializers.ValidationError({field_name: 'شناسه باید عدد صحیح مثبت باشد.'})
        if item_id in normalized:
            raise serializers.ValidationError({field_name: 'شناسه تکراری مجاز نیست.'})
        normalized.append(item_id)
    return normalized


def _apply_customer_profile_changes(subscription, customer_changes, operation):
    """Validate and persist shared customer data, with a contract audit trail."""
    if customer_changes is None:
        return
    if not isinstance(customer_changes, dict):
        raise serializers.ValidationError({
            'customer_changes': 'اطلاعات مشتری باید به‌صورت یک شیء ارسال شود.'
        })
    if not customer_changes:
        return

    if subscription.customer_type == 'organization':
        target = subscription.organization
        change_serializer_class = SubscriptionOrganizationCustomerChangeSerializer
        entity_type = 'Organization'
    else:
        target = subscription.user
        change_serializer_class = SubscriptionPersonalCustomerChangeSerializer
        entity_type = 'User'

    if target is None:
        raise serializers.ValidationError({'customer_changes': 'مشتری قرارداد یافت نشد'})
    # The organization/user profile is shared by all contracts; lock it so
    # concurrent edits cannot overwrite each other's validated changes.
    target = target.__class__.objects.select_for_update().get(pk=target.pk)

    change_serializer = change_serializer_class(
        target, data=customer_changes, partial=True
    )
    unknown_fields = set(customer_changes) - set(change_serializer.fields)
    if unknown_fields:
        raise serializers.ValidationError({
            'customer_changes': f'فیلدهای غیرمجاز: {", ".join(sorted(unknown_fields))}'
        })
    change_serializer.is_valid(raise_exception=True)

    for field, new_value in change_serializer.validated_data.items():
        old_value = getattr(target, field)
        if str(old_value) == str(new_value):
            continue
        SubscriptionOperationChange.objects.create(
            operation=operation,
            entity_type=entity_type,
            field_name=field,
            old_value='' if old_value is None else str(old_value),
            new_value='' if new_value is None else str(new_value),
        )
    change_serializer.save()


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

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        # Acquire the row lock in the initial lookup. A second concurrent
        # delete then waits and receives a normal 404 after the first commits,
        # rather than racing between get_object() and the lock query.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs[lookup_url_kwarg]
        branch = self.filter_queryset(self.get_queryset()).select_for_update().filter(
            **{self.lookup_field: lookup_value}
        ).first()
        if branch is None:
            from rest_framework.exceptions import NotFound
            raise NotFound()
        self.check_object_permissions(request, branch)

        references = []
        for relation in Branch._meta.related_objects:
            related_model = relation.related_model
            relation_field = relation.field
            count = related_model._base_manager.filter(
                **{relation_field.name: branch}
            ).count()
            if count:
                references.append({
                    'model': str(related_model._meta.verbose_name_plural),
                    'count': count,
                })

        if references:
            return Response(
                {
                    'detail': (
                        'این شعبه دارای کاربر، خودرو، دستگاه یا سابقه عملیاتی است '
                        'و حذف فیزیکی آن مجاز نیست. ابتدا وابستگی‌ها را از مسیرهای '
                        'مجاز مدیریت کنید یا وضعیت شعبه را غیرفعال کنید.'
                    ),
                    'references': references,
                },
                status=status.HTTP_409_CONFLICT,
            )

        self.perform_destroy(branch)
        return Response(status=status.HTTP_204_NO_CONTENT)

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
            if status_filter == 'expired':
                qs = qs.filter(
                    Q(status='expired')
                    | Q(status='active', end_date__lt=today)
                )
            elif status_filter == 'pending':
                qs = qs.filter(status='active', start_date__gt=today, end_date__gte=today)
            elif status_filter == 'active':
                qs = qs.filter(
                    status='active',
                    start_date__lte=today,
                    end_date__gte=today,
                )
            elif status_filter in {'suspended', 'cancelled'}:
                qs = qs.filter(status=status_filter)
            else:
                qs = qs.none()

        customer_type = self.request.query_params.get('customer_type')
        if customer_type:
            qs = qs.filter(customer_type=customer_type)

        organization_filter = self.request.query_params.get('organization')
        if organization_filter:
            qs = qs.filter(organization_id=organization_filter)

        expiring = self.request.query_params.get('expiring')
        if expiring == 'true':
            today = timezone.localdate()
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
        if notes is None:
            notes = ''
        if not isinstance(notes, str):
            raise serializers.ValidationError({'notes': 'یادداشت باید متن باشد.'})
        add_devices = request.data.get('add_devices', [])
        if add_devices is None:
            add_devices = []
        remove_ids = _validated_positive_id_list(
            request.data.get('remove_device_ids', []), 'remove_device_ids'
        )
        payments = request.data.get('payments', [])
        if not isinstance(payments, list) or any(not isinstance(item, dict) for item in payments):
            raise serializers.ValidationError({'payments': 'فهرست پرداخت‌ها نامعتبر است.'})
        if not new_end_date:
            return Response({'new_end_date': 'این فیلد الزامی است'}, status=status.HTTP_400_BAD_REQUEST)

        from datetime import date
        from .financial import allocate_payment
        try:
            new_end_date = date.fromisoformat(new_end_date)
        except (TypeError, ValueError):
            return Response({'new_end_date': 'فرمت تاریخ نامعتبر است'}, status=status.HTTP_400_BAD_REQUEST)

        if new_end_date <= timezone.localdate() or new_end_date <= subscription.end_date:
            return Response(
                {'new_end_date': 'تاریخ پایان جدید باید بعد از تاریخ پایان فعلی و در آینده باشد'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            _lock_subscription_devices(subscription, add_devices)
            subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)
            if new_end_date <= timezone.localdate() or new_end_date <= subscription.end_date:
                raise serializers.ValidationError({
                    'new_end_date': 'تاریخ پایان جدید باید بعد از تاریخ پایان فعلی و در آینده باشد'
                })
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

            # تمدید قرارداد باید وضعیت فعلی دستگاه‌های متصل را هم به پایان جدید منتقل کند.
            # چون end_date قرارداد از آخرین دستگاه فعال نیز محاسبه می‌شود،
            # اگر این کار انجام نشود، با ذخیره/تغییر بعدی ممکن است تاریخ تمدیدشده دوباره به تاریخ قبلی برگردد.
            subscription.subscription_devices.filter(
                unassigned_at__isnull=True
            ).exclude(id__in=remove_ids).update(end_date=new_end_date)

            subscription.end_date = new_end_date
            subscription.save(update_fields=['end_date', 'updated_at'])

            # دستگاه‌های جدید
            for item in add_devices:
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
            for link_id in remove_ids:
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
                _close_customer_access(link.device)
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
            for item in payments:
                payment_serializer = SubscriptionPaymentSerializer(
                    data={**item, 'subscription': subscription.id, 'operation': operation.id}
                )
                payment_serializer.is_valid(raise_exception=True)
                payment = payment_serializer.save()
                allocate_payment(payment)

            _apply_customer_profile_changes(
                subscription,
                request.data.get('customer_changes', {}),
                operation,
            )

        return Response(SubscriptionSerializer(subscription).data)

    @action(detail=True, methods=['post'])
    def modify(self, request, pk=None):
        """ویرایش قرارداد به‌عنوان یک SubscriptionOperation اتمیک."""
        subscription = self.get_object()

        contract_changes = request.data.get('contract_changes', {})
        customer_changes = request.data.get('customer_changes', {})
        payment_changes = request.data.get('payment_changes', [])
        add_devices = request.data.get('add_devices', [])
        if add_devices is None:
            add_devices = []
        remove_device_ids = _validated_positive_id_list(
            request.data.get('remove_device_ids', []), 'remove_device_ids'
        )
        notes = request.data.get('notes', '')
        if notes is None:
            notes = ''
        if not isinstance(notes, str):
            raise serializers.ValidationError({'notes': 'یادداشت باید متن باشد.'})
        if not isinstance(contract_changes, dict):
            raise serializers.ValidationError({
                'contract_changes': 'تغییرات قرارداد باید به‌صورت یک شیء ارسال شود.'
            })
        if not isinstance(payment_changes, list) or any(
            not isinstance(item, dict) for item in payment_changes
        ):
            raise serializers.ValidationError({
                'payment_changes': 'فهرست تغییرات پرداخت نامعتبر است.'
            })

        allowed_contract = {'start_date', 'end_date', 'notes'}
        if any(field not in allowed_contract for field in contract_changes):
            raise serializers.ValidationError({'contract_changes': 'فقط start_date، end_date و notes قابل ویرایش هستند'})

        from datetime import date
        parsed_contract = {}
        for field, value in contract_changes.items():
            if field in {'start_date', 'end_date'}:
                if not isinstance(value, str) or not value:
                    raise serializers.ValidationError({field: 'تاریخ الزامی و فرمت آن نامعتبر است'})
                try:
                    parsed_contract[field] = date.fromisoformat(value)
                except (TypeError, ValueError):
                    raise serializers.ValidationError({field: 'فرمت تاریخ نامعتبر است'})
            else:
                parsed_contract[field] = value

        new_start = parsed_contract.get('start_date', subscription.start_date)
        new_end = parsed_contract.get('end_date', subscription.end_date)
        if new_start > new_end:
            raise serializers.ValidationError({'contract_changes': 'تاریخ شروع قرارداد باید قبل از تاریخ پایان باشد'})

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
            _lock_subscription_devices(subscription, add_devices)
            subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)
            # Re-evaluate date bounds against the locked, current contract row.
            new_start = parsed_contract.get('start_date', subscription.start_date)
            new_end = parsed_contract.get('end_date', subscription.end_date)
            if new_start > new_end:
                raise serializers.ValidationError({'contract_changes': 'تاریخ شروع قرارداد باید قبل از تاریخ پایان باشد'})
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
            for link in subscription.subscription_devices.filter(unassigned_at__isnull=True).exclude(
                id__in=remove_device_ids
            ):
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
                _close_customer_access(link.device)
                record_device_lifecycle_event(
                    device=link.device,
                    event_type='removed_from_contract',
                    performed_by=request.user,
                    subscription=subscription,
                    organization=subscription.organization,
                    user=subscription.user,
                    description=f'دستگاه از قرارداد {subscription.contract_number} خارج شد؛ مالکیت دستگاه حفظ شد.',
                )

            _apply_customer_profile_changes(
                subscription, customer_changes, operation
            )

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
            subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)
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
            if subscription.status in {'cancelled', 'expired'}:
                return Response(
                    {'detail': 'قرارداد لغوشده یا منقضی‌شده قابل تعلیق نیست.'},
                    status=status.HTTP_409_CONFLICT,
                )
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
            subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)
            if subscription.status != 'suspended':
                return Response(
                    {'detail': 'فقط قرارداد تعلیق‌شده از این مسیر قابل فعال‌سازی است؛ قرارداد لغوشده یا منقضی نیازمند تمدید/فرآیند مستقل است.'},
                    status=status.HTTP_409_CONFLICT,
                )
            if subscription.end_date < timezone.localdate():
                return Response(
                    {'detail': 'قرارداد منقضی‌شده از مسیر فعال‌سازی عادی قابل بازگشت نیست.'},
                    status=status.HTTP_409_CONFLICT,
                )
            operation = SubscriptionOperation.objects.create(
                subscription=subscription, operation_type='activate',
                performed_by=request.user, old_status=subscription.status, new_status='active'
            )
            subscription.status = 'active'
            subscription.save(update_fields=['status', 'updated_at'])
        return Response(SubscriptionSerializer(subscription).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """لغو قرارداد و پایان‌دادن به تخصیص دستگاه‌های فعال آن."""
        subscription = self.get_object()
        with transaction.atomic():
            _lock_subscription_devices(subscription)
            subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)
            if subscription.status == 'cancelled':
                return Response(
                    {'detail': 'این قرارداد قبلاً لغو شده است.'},
                    status=status.HTTP_409_CONFLICT,
                )
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
                _close_customer_access(link.device)
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
            now = timezone.now()
            if user.is_site_admin:
                qs = qs.filter(
                    pk__in=active_subscription_links(now=now).values('pk')
                )
            elif user.is_main_user and user.organization_id:
                access = active_customer_access_periods(
                    organization_id=user.organization_id,
                    now=now,
                ).filter(
                    device_id=OuterRef('device_id'),
                    subscription_id=OuterRef('subscription_id'),
                )
                qs = qs.filter(Exists(access))
            elif user.is_personal_user:
                qs = qs.filter(
                    pk__in=active_personal_contract_links(
                        user_id=user.pk, now=now
                    ).values('pk')
                )
            else:
                qs = qs.none()

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
            device = Device.objects.select_for_update().get(
                pk=serializer.validated_data['device'].pk
            )
            subscription = Subscription.objects.select_for_update().get(
                pk=subscription.pk
            )
            from fleet.device_operations import _validate_device_customer_assignment
            _validate_device_customer_assignment(device, subscription)
            start_date = serializer.validated_data['start_date']
            end_date = serializer.validated_data['end_date']
            if (
                start_date < subscription.start_date
                or end_date > subscription.end_date
                or start_date > end_date
            ):
                raise serializers.ValidationError({
                    'non_field_errors': 'بازه اتصال دستگاه باید کاملاً داخل بازه قرارداد باشد.'
                })
            operation = SubscriptionOperation.objects.create(
                subscription=subscription,
                operation_type='add_device',
                performed_by=request.user,
                old_end_date=subscription.end_date,
                new_end_date=subscription.end_date,
            )
            instance = serializer.save(
                device=device,
                subscription=subscription,
                added_by_operation=operation,
            )
        return Response(self.get_serializer(instance).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        """خروج دستگاه از قرارداد؛ مالکیت دستگاه حفظ می‌شود."""
        instance = self.get_object()
        subscription = instance.subscription
        with transaction.atomic():
            Device.objects.select_for_update().get(pk=instance.device_id)
            subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)
            instance = SubscriptionDevice.objects.select_for_update().get(pk=instance.pk)
            if instance.unassigned_at is not None:
                return Response(
                    {'detail': 'این دستگاه قبلاً از قرارداد خارج شده است.'},
                    status=status.HTTP_409_CONFLICT,
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
            _close_customer_access(instance.device)

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