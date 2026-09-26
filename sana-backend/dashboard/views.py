from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

from accounts.models import User
from organizations.models import Organization, Branch, Subscription
from fleet.models import Vehicle, Device, Driver


class DashboardStatsView(APIView):
    """آمار داشبورد بر اساس نقش کاربر"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.now().date()
        thirty_days_later = today + timedelta(days=30)

        # ادمین کل سایت
        if user.is_site_admin:
            # قراردادهای نزدیک به انقضا
            expiring_soon = Subscription.objects.filter(
                status='active',
                end_date__gte=today,
                end_date__lte=thirty_days_later,
            ).count()

            # قراردادهای منقضی شده ولی هنوز status=active
            expired = Subscription.objects.filter(
                status='active',
                end_date__lt=today,
            ).count()

            return Response({
                'companies': Organization.objects.count(),
                'vehicles': Vehicle.objects.count(),
                'devices': Device.objects.count(),
                'drivers': Driver.objects.count(),
                'users': User.objects.count(),
                'branches': Branch.objects.count(),
                'subscriptions_total': Subscription.objects.count(),
                'subscriptions_active': Subscription.objects.filter(status='active').count(),
                'subscriptions_expiring_soon': expiring_soon,
                'subscriptions_expired': expired,
                'devices_by_status': self.get_devices_by_status(None),
                'vehicles_by_status': self.get_vehicles_by_status(None),
            })

        # مدیر شرکت
        if user.is_main_user and user.organization_id:
            org = user.organization_id
            subscriptions = Subscription.objects.filter(organization_id=org)
            active_sub = subscriptions.filter(
                status='active',
                end_date__gte=today,
            ).order_by('-end_date').first()

            return Response({
                'vehicles': Vehicle.objects.filter(organization_id=org).count(),
                'devices': Device.objects.filter(organization_id=org).count(),
                'drivers': Driver.objects.filter(organization_id=org).count(),
                'users': User.objects.filter(organization_id=org).count(),
                'branches': Branch.objects.filter(organization_id=org).count(),
                'subscriptions_total': subscriptions.count(),
                'subscriptions_active': subscriptions.filter(status='active').count(),
                'subscriptions_expiring_soon': subscriptions.filter(
                    status='active',
                    end_date__gte=today,
                    end_date__lte=thirty_days_later,
                ).count(),
                'current_subscription': {
                    'contract_number': active_sub.contract_number,
                    'end_date': active_sub.end_date,
                    'days_until_expiry': active_sub.days_until_expiry,
                    'is_expiring_soon': active_sub.is_expiring_soon,
                } if active_sub else None,
                'devices_by_status': self.get_devices_by_status(org),
                'vehicles_by_status': self.get_vehicles_by_status(org),
            })

        # مدیر شعبه
        if user.is_branch_manager and user.branch_id:
            branch = user.branch_id
            org_id = user.organization_id
            subscriptions = Subscription.objects.filter(organization_id=org_id)
            active_sub = subscriptions.filter(
                status='active',
                end_date__gte=today,
            ).order_by('-end_date').first()

            return Response({
                'vehicles': Vehicle.objects.filter(branch_id=branch).count(),
                'devices': Device.objects.filter(branch_id=branch).count(),
                'drivers': Driver.objects.filter(branch_id=branch).count(),
                'current_subscription': {
                    'contract_number': active_sub.contract_number,
                    'end_date': active_sub.end_date,
                    'days_until_expiry': active_sub.days_until_expiry,
                    'is_expiring_soon': active_sub.is_expiring_soon,
                } if active_sub else None,
                'devices_by_status': self.get_devices_by_status(branch=branch),
                'vehicles_by_status': self.get_vehicles_by_status(branch=branch),
            })

        # مشتری شخصی
        if user.is_personal_user:
            subscriptions = Subscription.objects.filter(user=user)
            active_sub = subscriptions.filter(
                status='active',
                end_date__gte=today,
            ).order_by('-end_date').first()

            return Response({
                'vehicles': Vehicle.objects.filter(owner_user=user).count(),
                'devices': Device.objects.filter(owner_user=user).count(),
                'subscriptions_total': subscriptions.count(),
                'current_subscription': {
                    'contract_number': active_sub.contract_number,
                    'end_date': active_sub.end_date,
                    'days_until_expiry': active_sub.days_until_expiry,
                    'is_expiring_soon': active_sub.is_expiring_soon,
                } if active_sub else None,
                'devices_by_status': self.get_devices_by_status(owner=user),
                'vehicles_by_status': self.get_vehicles_by_status(owner=user),
            })

        return Response({
            'vehicles': 0,
            'devices': 0,
        })

    def get_devices_by_status(self, org=None, branch=None, owner=None):
        qs = Device.objects.all()
        if org:
            qs = qs.filter(organization_id=org)
        if branch:
            qs = qs.filter(branch_id=branch)
        if owner:
            qs = qs.filter(owner_user=owner)

        result = qs.values('management_status').annotate(count=Count('id'))
        return {item['management_status']: item['count'] for item in result}

    def get_vehicles_by_status(self, org=None, branch=None, owner=None):
        qs = Vehicle.objects.all()
        if org:
            qs = qs.filter(organization_id=org)
        if branch:
            qs = qs.filter(branch_id=branch)
        if owner:
            qs = qs.filter(owner_user=owner)

        result = {
            'with_device': qs.filter(devices__isnull=False).distinct().count(),
            'without_device': qs.filter(devices__isnull=True).count(),
        }
        return result