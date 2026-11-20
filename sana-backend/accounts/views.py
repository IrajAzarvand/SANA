from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from django.utils import timezone
from django.db.models import Q, Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from datetime import datetime, timedelta

from .models import User, UserSession, NotificationReadState
from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    UserProfileUpdateSerializer,
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
)
from .permissions import IsSiteAdminOrReadOnly

from organizations.models import (
    Organization, Branch, Subscription, SubscriptionOperation,
    SubscriptionPayment, SubscriptionInstallment,
)
from fleet.models import Device, DeviceOperation, DeviceLifecycleEvent


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
        elif user.is_main_user and user.organization:
            qs = User.objects.filter(organization=user.organization)
        # مدیر شعبه فقط کاربران شعبه خودش
        elif user.is_branch_manager and user.branch:
            qs = User.objects.filter(branch=user.branch)
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
            qs = qs.filter(organization_id=organization)

        return qs.select_related('organization', 'branch')

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
        return Response(UserSerializer(request.user).data)


    @action(detail=False, methods=['get', 'post'], url_path='notifications', throttle_classes=[ScopedRateThrottle], throttle_scope='panel_notifications')
    def notifications(self, request):
        """Return real, role-scoped operational events with per-user read state."""
        user = request.user

        if request.method == 'POST':
            if request.data.get('mark_all') is True:
                visible_keys = [
                    item['id'] for item in self._build_panel_notifications(user)
                ]
                NotificationReadState.objects.bulk_create(
                    [
                        NotificationReadState(user=user, event_key=event_key)
                        for event_key in visible_keys
                    ],
                    ignore_conflicts=True,
                )
                return Response({'updated': len(visible_keys)})

            event_key = str(request.data.get('event_key') or '').strip()
            if not event_key or len(event_key) > 200:
                return Response({'detail': 'شناسه اعلان نامعتبر است.'}, status=400)
            # Only allow marking an event that is currently visible to this user.
            visible_keys = {item['id'] for item in self._build_panel_notifications(user)}
            if event_key not in visible_keys:
                return Response({'detail': 'اعلان یافت نشد یا دسترسی ندارید.'}, status=404)
            state, _ = NotificationReadState.objects.update_or_create(
                user=user, event_key=event_key, defaults={'read_at': timezone.now()}
            )
            return Response({'id': state.event_key, 'is_read': True, 'read_at': state.read_at})

        events = self._build_panel_notifications(user)
        keys = [item['id'] for item in events]
        read_keys = set(NotificationReadState.objects.filter(
            user=user, event_key__in=keys
        ).values_list('event_key', flat=True))
        for item in events:
            item['is_read'] = item['id'] in read_keys
        return Response({
            'results': events,
            'counts': {
                'all': len(events),
                'unread': sum(not item['is_read'] for item in events),
                'read': sum(item['is_read'] for item in events),
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
            devices = Device.objects.none()
            subscription_ops = SubscriptionOperation.objects.select_related(
                'subscription', 'subscription__user', 'performed_by'
            ).filter(subscription__user=user, performed_at__gte=cutoff)
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
                customer_access_periods__organization_id=organization_id,
                customer_access_periods__started_at__lte=now,
                customer_access_periods__ended_at__isnull=True,
            ).distinct()
            subscription_ops = SubscriptionOperation.objects.select_related(
                'subscription', 'subscription__organization', 'performed_by'
            ).filter(subscription__organization_id=organization_id, performed_at__gte=cutoff)
        elif is_branch:
            organization_id = user.branch.organization_id if user.branch_id else user.organization_id
            branch_id = user.branch_id
            subscriptions = Subscription.objects.filter(
                organization_id=organization_id, customer_type='organization'
            )
            organizations = Organization.objects.none()
            branches = Branch.objects.filter(pk=branch_id) if branch_id else Branch.objects.none()
            users = User.objects.filter(branch_id=branch_id).exclude(pk=user.pk) if branch_id else User.objects.none()
            devices = Device.objects.filter(
                customer_access_periods__organization_id=organization_id,
                customer_access_periods__branch_id=branch_id,
                customer_access_periods__started_at__lte=now,
                customer_access_periods__ended_at__isnull=True,
            ).distinct() if branch_id else Device.objects.none()
            # Subscription access is organization-scoped in SubscriptionViewSet, so keep
            # contract/financial notifications consistent with that read-only API scope.
            subscription_ops = SubscriptionOperation.objects.select_related(
                'subscription', 'subscription__organization', 'performed_by'
            ).filter(subscription__organization_id=organization_id, performed_at__gte=cutoff)
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
                    f'مانده {remaining:,.0f} ریال'
                )
            elif days_until_due <= 7:
                stage = 'due-soon'
                title = 'سررسید قسط نزدیک است'
                message = (
                    f'قرارداد {subscription.contract_number} · قسط {installment.number} · '
                    f'مانده {remaining:,.0f} ریال · {days_until_due} روز تا سررسید'
                )
            else:
                continue
            add(
                f'installment:{installment.pk}:plan-{installment.plan_id}:{installment.due_date}:{stage}',
                title,
                message,
                timezone.make_aware(datetime.combine(installment.due_date, datetime.min.time())),
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
        if is_main:
            device_operations = device_operations.filter(
                Q(device__in=devices) | Q(target_organization_id=user.organization_id)
            )
            lifecycle_events = lifecycle_events.filter(
                Q(device__in=devices) | Q(organization_id=user.organization_id)
            )
        elif is_branch:
            device_operations = device_operations.filter(
                Q(device__in=devices) | Q(target_branch_id=user.branch_id)
            )
            lifecycle_events = lifecycle_events.filter(
                Q(device__in=devices) | Q(branch_id=user.branch_id)
            )

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
                f'چرخه عمر دستگاه: {event.get_event_type_display()}',
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
