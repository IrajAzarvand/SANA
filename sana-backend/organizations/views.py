from django.utils import timezone
from datetime import timedelta
from rest_framework import viewsets, filters, status
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
    SubscriptionRenewal,
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
    SubscriptionRenewSerializer,
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
        if self.action in ['create', 'destroy']:
            return [IsSiteAdmin()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        """ساخت قرارداد با Wizard"""
        serializer = SubscriptionWizardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription = serializer.save()

        # برگرداندن اطلاعات کامل
        response_serializer = SubscriptionSerializer(subscription)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def renew(self, request, pk=None):
        """تمدید قرارداد — بدون تغییر notes قرارداد، با ثبت تاریخچه"""
        subscription = self.get_object()

        # پاس دادن subscription به serializer برای validation
        serializer = SubscriptionRenewSerializer(
            data=request.data,
            context={'subscription': subscription}
        )
        serializer.is_valid(raise_exception=True)

        old_end_date = subscription.end_date
        new_end_date = serializer.validated_data['new_end_date']

        # ۱. آپدیت قرارداد (فقط end_date)
        subscription.end_date = new_end_date
        subscription.save()

        # ۲. ذخیره تاریخچه تمدید
        SubscriptionRenewal.objects.create(
            subscription=subscription,
            old_end_date=old_end_date,
            new_end_date=new_end_date,
            notes=serializer.validated_data.get('notes', ''),
            renewed_by=request.user if request.user.is_authenticated else None,
        )

        return Response(SubscriptionSerializer(subscription).data)

    

    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        """تعلیق قرارداد"""
        subscription = self.get_object()
        subscription.status = 'suspended'
        subscription.save()
        return Response(SubscriptionSerializer(subscription).data)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """فعال‌سازی مجدد قرارداد"""
        subscription = self.get_object()
        subscription.status = 'active'
        subscription.save()
        return Response(SubscriptionSerializer(subscription).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """لغو قرارداد"""
        subscription = self.get_object()
        subscription.status = 'cancelled'
        subscription.save()
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

    def destroy(self, request, *args, **kwargs):
        """قبل از حذف، unassigned_at رو ست کن"""
        instance = self.get_object()
        from django.utils import timezone
        instance.unassigned_at = timezone.now()
        instance.save()

        # برگرداندن دستگاه به انبار
        device = instance.device
        # اگه هیچ اتصال فعال دیگه‌ای نداره، برگردون به انبار
        other_active = device.subscription_links.filter(unassigned_at__isnull=True).exclude(id=instance.id).exists()
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

    def get_permissions(self):
        if self.action in ['create', 'destroy', 'update', 'partial_update']:
            return [IsSiteAdmin()]
        return super().get_permissions()