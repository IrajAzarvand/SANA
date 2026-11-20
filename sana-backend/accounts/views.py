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

from .models import User, UserSession
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
