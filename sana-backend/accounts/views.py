from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from django.utils import timezone
from django.db.models import Exists, OuterRef, Q, Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from datetime import datetime, timedelta

from .models import User, UserSession
from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    UserProfileUpdateSerializer,
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
)
from .permissions import IsSiteAdminOrReadOnly, IsMainUserOrSiteAdmin

from organizations.models import (
    SubscriptionDevice,
    Organization, Branch, Subscription, SubscriptionOperation,
    SubscriptionPayment, SubscriptionInstallment,
)
from fleet.customer_access import active_customer_access_periods, active_personal_contract_links
from fleet.models import Device, DeviceOperation, DeviceLifecycleEvent, DeviceAlertState


class CustomTokenObtainPairView(TokenObtainPairView):
    """لاگین با JWT — پاسخ شامل اطلاعات کاربر"""
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth_login'


class CustomTokenRefreshView(TokenRefreshView):
    """Rate-limit refresh-token rotation to reduce automated abuse."""
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth_refresh'


class UserViewSet(viewsets.ModelViewSet):
    # Declare the attribute so DRF's router accepts action-level throttle_scope overrides.
    throttle_scope = None
    queryset = User.objects.select_related('organization', 'branch').all()
    permission_classes = [IsAuthenticated, IsSiteAdminOrReadOnly]

    def get_permissions(self):
        if getattr(self, 'action', None) in ['create', 'update', 'partial_update', 'destroy', 'archive', 'restore']:
            return [IsAuthenticated(), IsMainUserOrSiteAdmin()]

        # The self-profile endpoint is safe for every authenticated role;
        # its serializer limits writes to the current user's contact details.
        if getattr(self, 'action', None) in ['me', 'change_password', 'notifications']:
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == 'me' and self.request.method == 'PATCH':
            return UserProfileUpdateSerializer
        if self.action == 'create':
            return UserCreateSerializer
        if self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserSerializer

    def get_queryset(self):
        user = self.request.user

        # ادمین کل سایت همه رو می‌بینه
        if user.is_site_admin:
            qs = User.objects.all()
        # مدیر شرکت فقط کاربران سازمان خودش
        elif user.is_main_user and user.organization_id:
            # Include directly linked users and legacy branch managers whose
            # organization FK is empty and whose branch belongs to this tenant.
            # A conflicting direct organization FK must never be overridden by
            # a branch relation pointing at another tenant.
            qs = User.objects.filter(
                role='branch_manager',
            ).filter(
                Q(organization_id=user.organization_id)
                | Q(organization__isnull=True, branch__organization_id=user.organization_id)
            ).filter(
                Q(organization__isnull=True)
                | ~Q(organization_id__in=Organization.objects.filter(status='archived').values('pk'))
            ).filter(
                Q(branch__isnull=True)
                | ~Q(branch__organization_id__in=Organization.objects.filter(status='archived').values('pk'))
            ).distinct()
        # مدیر شعبه فقط کاربران شعبه خودش
        elif user.is_branch_manager and user.branch:
            qs = User.objects.filter(id=user.id)
        # کاربر شخصی فقط خودش
        else:
            qs = User.objects.filter(id=user.id)

        # فیلترها
        role = self.request.query_params.get('role')
        if role:
            qs = qs.filter(role=role)

        account_type = self.request.query_params.get('account_type')
        if account_type:
            qs = qs.filter(account_type=account_type)

        organization = self.request.query_params.get('organization')
        if organization:
            qs = qs.filter(
                Q(organization_id=organization)
                | Q(organization__isnull=True, branch__organization_id=organization)
            ).distinct()

        if user.is_main_user:
            qs = qs.exclude(role__in=['site_admin', 'main_user'])
        archived = self.request.query_params.get('archived')
        if archived == 'true' or self.action == 'restore':
            qs = qs.filter(archived_at__isnull=False)
        else:
            qs = qs.filter(archived_at__isnull=True)
        return qs.select_related('organization', 'branch', 'archived_by')

    def perform_update(self, serializer):
        instance = serializer.save()
        if not instance.is_active:
            UserSession.objects.filter(user=instance, revoked_at__isnull=True).update(revoked_at=timezone.now())

    def perform_destroy(self, instance):
        self._archive_user(instance)

    def _archive_user(self, instance):
        if instance.pk == self.request.user.pk:
            from rest_framework.exceptions import ValidationError
            raise ValidationError('امکان بایگانی حساب کاربری خودتان وجود ندارد.')
        now = timezone.now()
        if instance.archived_at is None:
            instance.archived_was_active = instance.is_active
            instance.archived_at = now
            instance.archived_by = self.request.user
            instance.is_active = False
            instance.save(update_fields=['archived_was_active', 'archived_at', 'archived_by', 'is_active', 'updated_at'])
            UserSession.objects.filter(user=instance, revoked_at__isnull=True).update(revoked_at=now)

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        user = self.get_object()
        self._archive_user(user)
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        user = self.get_object()
        if user.archived_at is None:
            return Response({'detail': 'این کاربر بایگانی نشده است.'}, status=status.HTTP_409_CONFLICT)
        user.is_active = user.archived_was_active
        user.archived_at = None
        user.archived_by = None
        user.save(update_fields=['is_active', 'archived_at', 'archived_by', 'updated_at'])
        return Response(UserSerializer(user).data)

    @action(detail=False, methods=['get'], url_path='username-availability')
    def username_availability(self, request):
        """Check username uniqueness across every account type without exposing user data."""
        if not request.user.is_site_admin:
            return Response(
                {'detail': 'اجازه دسترسی به این بررسی را ندارید'},
                status=status.HTTP_403_FORBIDDEN,
            )

        username = str(request.query_params.get('username', '') or '').strip()
        if not username:
            return Response(
                {'detail': 'نام کاربری الزامی است'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        exists = User.objects.filter(username=username).exists()
        return Response({'available': not exists, 'exists': exists})

    @action(detail=False, methods=['get', 'patch'])
    def me(self, request):
        """Read or update the authenticated user's own profile."""
        if request.method == 'PATCH':
            serializer = UserProfileUpdateSerializer(
                request.user,
                data=request.data,
                partial=True,
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
        return Response(UserSerializer(request.user, context={'request': request}).data)


    @action(detail=False, methods=['get', 'post'], url_path='notifications', throttle_classes=[ScopedRateThrottle], throttle_scope='panel_notifications')
    def notifications(self, request):
        """Unified business notification API backed by fleet.DeviceAlertState."""
        user = request.user
        events = self._build_panel_notifications(user)
        keys = [item['id'] for item in events]

        if request.method == 'POST':
            now = timezone.now()
            if request.data.get('mark_all') is True:
                updated = 0
                for item in events:
                    state, created = DeviceAlertState.objects.get_or_create(
                        user=user,
                        event_key=item['id'],
                        defaults={
                            'notification_type': item.get('kind', 'business'),
                            'event_type': item.get('kind', 'business'),
                            'event_time': item['created_at'],
                            'status': 'read',
                            'read_at': now,
                        },
                    )
                    if not created and state.status == 'unread':
                        state.status = 'read'
                        state.read_at = now
                        state.save(update_fields=['status', 'read_at'])
                    updated += 1
                return Response({'updated': updated})

            event_key = str(request.data.get('event_key') or '').strip()
            requested_status = str(request.data.get('status') or 'read').strip()
            if requested_status not in {'read', 'reviewed', 'resolved'} or not event_key or len(event_key) > 200:
                return Response({'detail': 'شناسه اعلان یا وضعیت نامعتبر است.'}, status=400)
            item = next((event for event in events if event['id'] == event_key), None)
            if item is None:
                return Response({'detail': 'اعلان یافت نشد یا دسترسی ندارید.'}, status=404)
            defaults = {
                'notification_type': item.get('kind', 'business'),
                'event_type': item.get('kind', 'business'),
                'event_time': item['created_at'],
                'status': requested_status,
            }
            if requested_status in {'read', 'reviewed', 'resolved'}:
                defaults['read_at'] = now
            if requested_status in {'reviewed', 'resolved'}:
                defaults['reviewed_at'] = now
            if requested_status == 'resolved':
                defaults['resolved_at'] = now
            state = DeviceAlertState.objects.filter(user=user, event_key=event_key).first()
            if state is None:
                state = DeviceAlertState.objects.create(user=user, event_key=event_key, **defaults)
            elif state.status != 'resolved':
                allowed_from = {
                    'read': {'unread', 'read'},
                    'reviewed': {'unread', 'read', 'reviewed'},
                    'resolved': {'unread', 'read', 'reviewed'},
                }
                if state.status in allowed_from.get(requested_status, set()):
                    defaults['read_at'] = state.read_at or now if requested_status in {'read', 'reviewed', 'resolved'} else state.read_at
                    defaults['reviewed_at'] = state.reviewed_at or now if requested_status in {'reviewed', 'resolved'} else state.reviewed_at
                    defaults['resolved_at'] = state.resolved_at or now if requested_status == 'resolved' else state.resolved_at
                    for field, value in defaults.items():
                        setattr(state, field, value)
                    state.save()
            return Response({
                'id': state.event_key,
                'status': state.status,
                'is_read': state.status != 'unread',
                'read_at': state.read_at,
                'reviewed_at': state.reviewed_at,
                'resolved_at': state.resolved_at,
            })

        state_by_key = {
            state.event_key: state
            for state in DeviceAlertState.objects.filter(user=user, event_key__in=keys)
        }
        for item in events:
            state = state_by_key.get(item['id'])
            item['status'] = state.status if state else 'unread'
            item['is_read'] = bool(state and state.status != 'unread')
            item['read_at'] = state.read_at if state else None
            item['reviewed_at'] = state.reviewed_at if state else None
            item['resolved_at'] = state.resolved_at if state else None
        return Response({
            'results': events,
            'counts': {
                'all': len(events),
                'unread': sum(item['status'] == 'unread' for item in events),
                'read': sum(item['status'] == 'read' for item in events),
                'reviewed': sum(item['status'] == 'reviewed' for item in events),
                'resolved': sum(item['status'] == 'resolved' for item in events),
            },
        })

    @staticmethod
    def _build_panel_notifications(user):
        """Build persisted business events and current financial reminders within the user's tenant."""
        now = timezone.now()
        today = timezone.localdate()
        cutoff = now - timedelta(days=30)
        is_admin = user.is_site_admin
        is_personal = user.is_personal_user
        is_main = user.is_main_user and bool(user.organization_id)
        is_branch = user.is_branch_manager and bool(user.branch_id)

        if is_admin:
            subscriptions = Subscription.objects.all()
            organizations = Organization.objects.all()
            branches = Branch.objects.all()
            users = User.objects.exclude(pk=user.pk)
            devices = Device.objects.all()
            subscription_ops = SubscriptionOperation.objects.select_related(
                'subscription', 'subscription__organization', 'subscription__user', 'performed_by'
            ).filter(performed_at__gte=cutoff)
        elif is_personal:
            subscriptions = Subscription.objects.filter(user=user, customer_type='personal')
            organizations = Organization.objects.none()
            branches = Branch.objects.none()
            users = User.objects.none()
            # Only devices covered by a currently valid personal contract
            # and a currently valid device-to-contract assignment belong in
            # the customer's present-day business notification scope.
            devices = Device.objects.filter(
                pk__in=active_personal_contract_links(
                    user_id=user.pk, now=now
                ).values('device_id')
            )
            subscription_ops = SubscriptionOperation.objects.select_related(
                'subscription', 'subscription__user', 'performed_by'
            ).filter(subscription__in=subscriptions, performed_at__gte=cutoff)
        elif is_main:
            organization_id = user.organization_id
            subscriptions = Subscription.objects.filter(
                organization_id=organization_id, customer_type='organization'
            )
            organizations = Organization.objects.filter(pk=organization_id)
            branches = Branch.objects.filter(organization_id=organization_id)
            users = User.objects.filter(
                Q(organization_id=organization_id) | Q(branch__organization_id=organization_id)
            ).exclude(pk=user.pk)
            devices = Device.objects.filter(
                pk__in=active_customer_access_periods(
                    organization_id=organization_id, now=now
                ).values('device_id')
            )
            subscription_ops = SubscriptionOperation.objects.select_related(
                'subscription', 'subscription__organization', 'performed_by'
            ).filter(subscription__organization_id=organization_id, performed_at__gte=cutoff)
        elif is_branch:
            organization_id = user.branch.organization_id if user.branch_id else user.organization_id
            branch_id = user.branch_id
            subscriptions = Subscription.objects.none()
            organizations = Organization.objects.none()
            branches = Branch.objects.filter(pk=branch_id) if branch_id else Branch.objects.none()
            users = User.objects.none()
            devices = Device.objects.filter(
                pk__in=active_customer_access_periods(
                    organization_id=organization_id,
                    branch_id=branch_id,
                    now=now,
                ).values('device_id')
            ) if branch_id else Device.objects.none()
            # Branch managers must not receive contract lifecycle or financial events.
            subscription_ops = SubscriptionOperation.objects.none()
        else:
            return []

        items = []

        def add(key, title, message, timestamp, path, *, persistent=False, kind='business'):
            if timestamp and (persistent or timestamp >= cutoff):
                items.append({
                    'id': key,
                    'title': title,
                    'message': message,
                    'created_at': timestamp,
                    'path': path,
                    'kind': kind,
                })

        # Contract lifecycle and management operations.
        for operation in subscription_ops.exclude(operation_type='payment')[:200]:
            subscription = operation.subscription
            customer_name = (
                subscription.organization.name if subscription.organization_id
                else (subscription.user.full_name or subscription.user.username if subscription.user_id else 'مشتری')
            )
            add(
                f'subscription-operation:{operation.pk}',
                f'قرارداد: {operation.get_operation_type_display()}',
                f'{subscription.contract_number} · {customer_name}',
                operation.performed_at,
                f'/panel/subscriptions/{subscription.pk}',
            )

        # Real receipts are distinct from installment reminders and are visible only
        # to the contract owner/tenant and site administrators.
        payments = SubscriptionPayment.objects.select_related(
            'subscription', 'subscription__organization', 'subscription__user'
        ).filter(subscription__in=subscriptions, created_at__gte=cutoff).order_by('-created_at')
        for payment in payments[:200]:
            subscription = payment.subscription
            add(
                f'payment-received:{payment.pk}',
                'پرداخت قرارداد ثبت شد',
                f'قرارداد {subscription.contract_number} · مبلغ {payment.amount:,.0f} ریال',
                payment.created_at,
                f'/panel/subscriptions/{subscription.pk}',
                kind='financial',
            )

        # Current active schedule only: superseded plans disappear from the feed.
        # Allocation totals ensure a fully-paid installment never generates a reminder.
        installments = SubscriptionInstallment.objects.filter(
            plan__subscription__in=subscriptions,
            plan__subscription__status='active',
            plan__status='active',
            status='active',
        ).select_related('plan', 'plan__subscription').annotate(
            allocated_amount=Coalesce(
                Sum('allocations__amount'),
                Value(0),
                output_field=DecimalField(max_digits=15, decimal_places=0),
            )
        ).order_by('due_date', 'number')

        for installment in installments:
            remaining = (installment.amount or 0) - (installment.allocated_amount or 0)
            if remaining <= 0:
                continue
            subscription = installment.plan.subscription
            days_until_due = (installment.due_date - today).days
            if days_until_due < 0:
                stage = 'overdue'
                title = 'قسط سررسیدگذشته و تسویه‌نشده'
                message = (
                    f'قرارداد {subscription.contract_number} · قسط {installment.number} · '
                    f'مانده {remaining:,.0f} ریال · سررسید {installment.due_date}'
                )
            elif days_until_due == 0:
                stage = 'due-today'
                title = 'سررسید قسط امروز است'
                message = (
                    f'قرارداد {subscription.contract_number} · قسط {installment.number} · '
                    f'مانده {remaining:,.0f} ریال · سررسید {installment.due_date}'
                )
            elif days_until_due <= 7:
                stage = 'due-soon'
                title = 'سررسید قسط نزدیک است'
                message = (
                    f'قرارداد {subscription.contract_number} · قسط {installment.number} · '
                    f'مانده {remaining:,.0f} ریال · سررسید {installment.due_date} · {days_until_due} روز باقی‌مانده'
                )
            else:
                continue
            add(
                f'installment:{installment.pk}:plan-{installment.plan_id}:{installment.due_date}:{stage}',
                title,
                message,
                now,
                f'/panel/subscriptions/{subscription.pk}',
                persistent=True,
                kind='financial',
            )

        # Contract expiry reminder: keep the existing 30-day dashboard policy and
        # provide a stable notification key so polling does not create duplicates.
        for subscription in subscriptions.filter(status='active', end_date__gte=today, end_date__lte=today + timedelta(days=30)):
            days_left = (subscription.end_date - today).days
            add(
                f'contract-expiring:{subscription.pk}:{subscription.end_date.isoformat()}',
                'موعد پایان قرارداد نزدیک است',
                f'قرارداد {subscription.contract_number} · {days_left} روز تا پایان قرارداد',
                now,
                f'/panel/subscriptions/{subscription.pk}',
                persistent=True,
                kind='financial',
            )

        for subscription in subscriptions.filter(
            status__in=['active', 'expired'],
            end_date__lt=today,
            end_date__gte=today - timedelta(days=30),
        ):
            expired_at = timezone.make_aware(datetime.combine(subscription.end_date, datetime.min.time()))
            add(
                f'contract-expired:{subscription.pk}:{subscription.end_date.isoformat()}',
                'قرارداد منقضی شده است',
                f'قرارداد {subscription.contract_number} در تاریخ {subscription.end_date} پایان یافته است',
                expired_at,
                f'/panel/subscriptions/{subscription.pk}',
                persistent=True,
                kind='financial',
            )

        # Active installment-plan revisions are explicit business events.
        for plan in subscriptions.filter(installment_plans__status='active').values_list(
            'installment_plans__id', 'installment_plans__version',
            'installment_plans__created_at', 'contract_number', 'id'
        ).distinct():
            plan_id, version, created_at, contract_number, subscription_id = plan
            add(
                f'installment-plan:{plan_id}',
                'برنامه اقساط قرارداد ثبت یا اصلاح شد',
                f'قرارداد {contract_number} · نسخه {version}',
                created_at,
                f'/panel/subscriptions/{subscription_id}',
                kind='financial',
            )

        # Organization, branch, user, and device activity remains role-scoped.
        device_operations = DeviceOperation.objects.select_related(
            'device', 'target_organization', 'target_branch', 'performed_by'
        ).filter(performed_at__gte=cutoff)
        lifecycle_events = DeviceLifecycleEvent.objects.select_related(
            'device', 'organization', 'branch', 'performed_by'
        ).filter(event_date__gte=cutoff, device_operation__isnull=True)
        if is_personal:
            # Historical device activity is visible only when this exact device
            # was assigned to one of this customer's personal contracts at the
            # time the event occurred. Current ownership alone is insufficient:
            # it would expose another customer's old device history after a transfer.
            operation_contract_access = SubscriptionDevice.objects.filter(
                device_id=OuterRef('device_id'),
                subscription__in=subscriptions,
                subscription__start_date__lte=OuterRef('performed_at__date'),
                subscription__end_date__gte=OuterRef('performed_at__date'),
                start_date__lte=OuterRef('performed_at__date'),
                end_date__gte=OuterRef('performed_at__date'),
                assigned_at__lte=OuterRef('performed_at'),
            ).filter(
                Q(unassigned_at__isnull=True)
                | Q(unassigned_at__gte=OuterRef('performed_at'))
            )
            lifecycle_contract_access = SubscriptionDevice.objects.filter(
                device_id=OuterRef('device_id'),
                subscription__in=subscriptions,
                subscription__start_date__lte=OuterRef('event_date__date'),
                subscription__end_date__gte=OuterRef('event_date__date'),
                start_date__lte=OuterRef('event_date__date'),
                end_date__gte=OuterRef('event_date__date'),
                assigned_at__lte=OuterRef('event_date'),
            ).filter(
                Q(unassigned_at__isnull=True)
                | Q(unassigned_at__gte=OuterRef('event_date'))
            )
            device_operations = device_operations.filter(Exists(operation_contract_access))
            lifecycle_events = lifecycle_events.filter(Exists(lifecycle_contract_access))
        elif is_main or is_branch:
            # Tenant/branch labels on an operation are not an independent
            # authorization grant. Device identifiers are visible only while
            # the device itself is inside the user's active access scope.
            device_operations = device_operations.filter(device__in=devices)
            lifecycle_events = lifecycle_events.filter(device__in=devices)

        for operation in device_operations[:100]:
            add(
                f'device-operation:{operation.pk}',
                f'دستگاه: {operation.get_operation_type_display()}',
                f'IMEI {operation.device.imei}' + (f' · {operation.description}' if operation.description else ''),
                operation.performed_at,
                '/panel/devices',
            )
        for event in lifecycle_events[:100]:
            add(
                f'device-lifecycle:{event.pk}',
                event.get_event_type_display(),
                f'IMEI {event.device.imei}' + (f' · {event.description}' if event.description else ''),
                event.event_date,
                '/panel/devices',
            )

        for organization in organizations:
            if is_admin and organization.created_at >= cutoff:
                add(f'organization-created:{organization.pk}', 'سازمان جدید ثبت شد', organization.name, organization.created_at, '/panel/companies')
            if organization.updated_at >= cutoff and organization.updated_at > organization.created_at + timedelta(seconds=1):
                add(f'organization-updated:{organization.pk}:{organization.updated_at.isoformat()}', 'اطلاعات سازمان به‌روزرسانی شد', organization.name, organization.updated_at, '/panel/companies' if is_admin else '/panel/settings')

        for branch in branches:
            if branch.created_at >= cutoff:
                add(f'branch-created:{branch.pk}', 'شعبه جدید ایجاد شد', branch.name, branch.created_at, '/panel/branches' if is_admin or is_main else '/panel/dashboard')
            if branch.updated_at >= cutoff and branch.updated_at > branch.created_at + timedelta(seconds=1):
                add(f'branch-updated:{branch.pk}:{branch.updated_at.isoformat()}', 'اطلاعات شعبه تغییر کرد', branch.name, branch.updated_at, '/panel/branches' if is_admin or is_main else '/panel/dashboard')

        for account in users:
            account_label = account.full_name or account.username
            if account.date_joined >= cutoff:
                add(f'user-created:{account.pk}', 'کاربر جدید اضافه شد', account_label, account.date_joined, '/panel/users' if is_admin or is_main else '/panel/dashboard')
            if account.updated_at >= cutoff and account.updated_at > account.date_joined + timedelta(seconds=1):
                add(
                    f'user-updated:{account.pk}:{account.updated_at.isoformat()}',
                    'اطلاعات کاربر به‌روزرسانی شد',
                    account_label,
                    account.updated_at,
                    '/panel/users' if is_admin or is_main else '/panel/dashboard',
                )

        items.sort(key=lambda item: item['created_at'], reverse=True)
        return items[:200]

    @action(detail=False, methods=['post'], throttle_classes=[ScopedRateThrottle], throttle_scope='password_change')
    def change_password(self, request):
        """Change the authenticated user's own password."""
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'رمز عبور با موفقیت تغییر کرد'})


class LogoutView(APIView):
    """Revoke the current browser/device session on the server."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = getattr(request.auth, 'payload', {}).get('sid')
        if session_id:
            UserSession.objects.filter(
                pk=session_id,
                user=request.user,
                revoked_at__isnull=True,
            ).update(revoked_at=timezone.now())
        return Response({'detail': 'از حساب کاربری خارج شدید.'})
