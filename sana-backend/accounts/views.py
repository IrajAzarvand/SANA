from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from django.utils import timezone
from django.db.models import Q
from datetime import timedelta

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

from organizations.models import Organization, Branch, SubscriptionOperation
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
        if user.is_personal_user:
            return Response({'results': [], 'counts': {'all': 0, 'unread': 0}})

        if request.method == 'POST':
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
        """Build notifications from persisted business/operation records, never placeholders."""
        cutoff = timezone.now() - timedelta(days=30)
        is_admin = user.is_site_admin
        is_main = user.is_main_user and bool(user.organization_id)
        is_branch = user.is_branch_manager and bool(user.branch_id)
        if not (is_admin or is_main or is_branch):
            return []

        if is_admin:
            devices = Device.objects.all()
            organizations = Organization.objects.all()
            branches = Branch.objects.all()
            users = User.objects.exclude(pk=user.pk)
            subscription_ops = SubscriptionOperation.objects.select_related(
                'subscription', 'subscription__organization', 'performed_by'
            ).filter(performed_at__gte=cutoff)
        elif is_main:
            organization_id = user.organization_id
            devices = Device.objects.filter(
                customer_access_periods__organization_id=organization_id,
                customer_access_periods__started_at__lte=timezone.now(),
                customer_access_periods__ended_at__isnull=True,
            ).distinct()
            organizations = Organization.objects.filter(pk=organization_id)
            branches = Branch.objects.filter(organization_id=organization_id)
            users = User.objects.filter(organization_id=organization_id).exclude(pk=user.pk)
            subscription_ops = SubscriptionOperation.objects.select_related(
                'subscription', 'subscription__organization', 'performed_by'
            ).filter(subscription__organization_id=organization_id, performed_at__gte=cutoff)
        else:
            branch_id = user.branch_id
            organization_id = user.branch.organization_id
            devices = Device.objects.filter(
                customer_access_periods__organization_id=organization_id,
                customer_access_periods__branch_id=branch_id,
                customer_access_periods__started_at__lte=timezone.now(),
                customer_access_periods__ended_at__isnull=True,
            ).distinct()
            organizations = Organization.objects.none()
            branches = Branch.objects.filter(pk=branch_id)
            users = User.objects.filter(branch_id=branch_id).exclude(pk=user.pk)
            subscription_ops = SubscriptionOperation.objects.select_related(\n                'subscription', 'subscription__organization', 'performed_by'\n            ).filter(subscription__organization_id=organization_id, performed_at__gte=cutoff)

        items = []

        def add(key, title, message, timestamp, path):
            if timestamp and timestamp >= cutoff:
                items.append({
                    'id': key,
                    'title': title,
                    'message': message,
                    'created_at': timestamp,
                    'path': path,
                })

        for operation in subscription_ops[:100]:
            organization_name = operation.subscription.organization.name if operation.subscription.organization_id else 'مشتری'
            add(
                f'subscription-operation:{operation.pk}',
                f'قرارداد: {operation.get_operation_type_display()}',
                f'{operation.subscription.contract_number} · {organization_name}',
                operation.performed_at,
                '/panel/subscriptions' if is_admin else '/panel/dashboard',
            )

        device_operations = DeviceOperation.objects.select_related(
            'device', 'target_organization', 'target_branch', 'performed_by'
        ).filter(performed_at__gte=cutoff)
        lifecycle_events = DeviceLifecycleEvent.objects.select_related(
            'device', 'organization', 'branch', 'performed_by'
        ).filter(event_date__gte=cutoff, device_operation__isnull=True)
        if is_main:
            device_operations = device_operations.filter(
                Q(device__in=devices) | Q(target_organization_id=organization_id)
            )
            lifecycle_events = lifecycle_events.filter(
                Q(device__in=devices) | Q(organization_id=organization_id)
            )
        elif is_branch:
            device_operations = device_operations.filter(
                Q(device__in=devices) | Q(target_branch_id=branch_id)
            )
            lifecycle_events = lifecycle_events.filter(
                Q(device__in=devices) | Q(branch_id=branch_id)
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
            if organization.created_at >= cutoff:
                add(f'organization-created:{organization.pk}', 'سازمان جدید ثبت شد', organization.name, organization.created_at, '/panel/companies')
            if organization.updated_at >= cutoff and organization.updated_at > organization.created_at:
                add(f'organization-updated:{organization.pk}:{organization.updated_at.isoformat()}', 'اطلاعات سازمان به‌روزرسانی شد', organization.name, organization.updated_at, '/panel/companies')

        for branch in branches:
            if branch.created_at >= cutoff:
                add(f'branch-created:{branch.pk}', 'شعبه جدید ایجاد شد', branch.name, branch.created_at, '/panel/branches' if is_admin or is_main else '/panel/dashboard')
            if branch.updated_at >= cutoff and branch.updated_at > branch.created_at:
                add(f'branch-updated:{branch.pk}:{branch.updated_at.isoformat()}', 'اطلاعات شعبه تغییر کرد', branch.name, branch.updated_at, '/panel/branches' if is_admin or is_main else '/panel/dashboard')

        for account in users:
            if account.date_joined >= cutoff:
                add(f'user-created:{account.pk}', 'کاربر جدید اضافه شد', account.full_name or account.username, account.date_joined, '/panel/users' if is_admin or is_main else '/panel/dashboard')

        items.sort(key=lambda item: item['created_at'], reverse=True)
        return items[:100]

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
