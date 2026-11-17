from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from datetime import timedelta

from accounts.models import User
from organizations.models import Organization, Branch, Subscription, SubscriptionDevice
from fleet.models import Vehicle, Device, Driver, DeviceCustomerAccessPeriod
from fleet.traccar_api import TraccarAPIError, traccar_current_positions, traccar_devices
from .models import SiteSettings


class DashboardStatsView(APIView):
    """آمار داشبورد بر اساس نقش کاربر"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.localdate()
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
                start_date__lte=today,
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
                start_date__lte=today,
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
            now = timezone.now()
            active_access = DeviceCustomerAccessPeriod.objects.filter(
                device=OuterRef('pk'),
                user=user,
                started_at__lte=now,
            ).filter(
                Q(ended_at__isnull=True) | Q(ended_at__gte=now)
            )
            active_contract_link = SubscriptionDevice.objects.filter(
                device=OuterRef('pk'),
                subscription__user=user,
                subscription__status='active',
                subscription__start_date__lte=today,
                subscription__end_date__gte=today,
                unassigned_at__isnull=True,
                start_date__lte=today,
                end_date__gte=today,
            )
            personal_devices = Device.objects.filter(
                Q(Exists(active_access)) | Q(Exists(active_contract_link))
            )
            subscriptions = Subscription.objects.filter(user=user)
            active_sub = subscriptions.filter(
                status='active',
                start_date__lte=today,
                end_date__gte=today,
            ).order_by('-end_date').first()

            personal_device_list = list(personal_devices.only('id', 'imei'))
            management_status = self.get_devices_by_status(access_user=user)
            gps_status = self.get_personal_gps_status(personal_device_list)

            return Response({
                'vehicles': Vehicle.objects.filter(owner_user=user).count(),
                'devices': len(personal_device_list),
                'subscriptions_total': subscriptions.count(),
                'current_subscription': {
                    'id': active_sub.id,
                    'contract_number': active_sub.contract_number,
                    'end_date': active_sub.end_date,
                    'days_until_expiry': active_sub.days_until_expiry,
                    'is_expiring_soon': active_sub.is_expiring_soon,
                } if active_sub else None,
                'devices_by_status': management_status,
                'devices_by_management_status': management_status,
                'gps_status': gps_status,
                'vehicles_by_status': self.get_vehicles_by_status(owner=user),
            })

        return Response({
            'vehicles': 0,
            'devices': 0,
        })

    @staticmethod
    def get_personal_gps_status(devices):
        """Summarize live GPS connectivity for only the customer's authorized devices."""
        total = len(devices)
        unavailable = {
            'available': False,
            'total': total,
            'online': None,
            'offline': None,
            'moving': None,
            'stopped': None,
        }
        if not total:
            return {
                **unavailable,
                'available': True,
                'online': 0,
                'offline': 0,
                'moving': 0,
                'stopped': 0,
            }

        try:
            traccar_device_list = traccar_devices()
            positions = traccar_current_positions()
        except TraccarAPIError:
            return unavailable

        authorized_by_imei = {str(device.imei).strip(): device for device in devices}
        traccar_by_id = {}
        for item in traccar_device_list:
            try:
                traccar_id = int(item['id'])
            except (KeyError, TypeError, ValueError):
                continue
            imei = str(item.get('uniqueId') or '').strip()
            if imei in authorized_by_imei:
                traccar_by_id[traccar_id] = item

        position_by_device = {}
        for position in positions:
            try:
                traccar_id = int(position['deviceId'])
            except (KeyError, TypeError, ValueError):
                continue
            if traccar_id not in traccar_by_id:
                continue
            received_at = parse_datetime(str(position.get('serverTime') or ''))
            if received_at is None:
                continue
            if timezone.is_naive(received_at):
                received_at = timezone.make_aware(received_at)
            previous = position_by_device.get(traccar_id)
            if previous is None or received_at > previous[0]:
                position_by_device[traccar_id] = (received_at, position)

        now = timezone.now()
        online = moving = stopped = 0
        for traccar_id, traccar_device in traccar_by_id.items():
            current = position_by_device.get(traccar_id)
            if (
                str(traccar_device.get('status') or '').lower() != 'online'
                or current is None
                or not 0 <= (now - current[0]).total_seconds() <= 300
            ):
                continue

            online += 1
            position = current[1]
            attributes = position.get('attributes') if isinstance(position.get('attributes'), dict) else {}
            try:
                speed_kmh = float(position.get('speed') or 0) * 1.852
            except (TypeError, ValueError):
                speed_kmh = 0
            if attributes.get('motion') is True or speed_kmh >= 3:
                moving += 1
            else:
                stopped += 1

        return {
            'available': True,
            'total': total,
            'online': online,
            'offline': total - online,
            'moving': moving,
            'stopped': stopped,
        }

    def get_devices_by_status(self, org=None, branch=None, owner=None, access_user=None):
        qs = Device.objects.all()
        if org:
            qs = qs.filter(organization_id=org)
        if branch:
            qs = qs.filter(branch_id=branch)
        if owner:
            qs = qs.filter(owner_user=owner)
        if access_user:
            now = timezone.now()
            today = timezone.localdate()
            active_access = DeviceCustomerAccessPeriod.objects.filter(
                device=OuterRef('pk'),
                user=access_user,
                started_at__lte=now,
            ).filter(
                Q(ended_at__isnull=True) | Q(ended_at__gte=now)
            )
            active_contract_link = SubscriptionDevice.objects.filter(
                device=OuterRef('pk'),
                subscription__user=access_user,
                subscription__status='active',
                subscription__start_date__lte=today,
                subscription__end_date__gte=today,
                unassigned_at__isnull=True,
                start_date__lte=today,
                end_date__gte=today,
            )
            qs = qs.filter(
                Q(Exists(active_access)) | Q(Exists(active_contract_link))
            )

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


class SiteSettingsView(APIView):
    """خواندن تنظیمات برای کاربران واردشده؛ ویرایش فقط توسط ادمین کل سایت."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        settings, _ = SiteSettings.objects.get_or_create(pk=1)
        return Response(self.serialize(settings))

    def patch(self, request):
        if not request.user.is_site_admin:
            return Response(
                {'detail': 'فقط ادمین کل سایت اجازه تغییر تنظیمات سامانه را دارد.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        settings, _ = SiteSettings.objects.get_or_create(pk=1)
        data = request.data
        allowed_fields = {'map_provider', 'map_refresh_interval_seconds'}
        unknown_fields = set(data.keys()) - allowed_fields
        if unknown_fields:
            return Response(
                {'detail': 'فیلدهای ارسال‌شده پشتیبانی نمی‌شوند.', 'fields': sorted(unknown_fields)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if 'map_provider' in data:
            provider = data['map_provider']
            valid_providers = {value for value, _ in SiteSettings.MAP_PROVIDER_CHOICES}
            if provider not in valid_providers:
                return Response(
                    {'map_provider': ['ارائه‌دهنده نقشه معتبر نیست.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            settings.map_provider = provider

        if 'map_refresh_interval_seconds' in data:
            try:
                interval = int(data['map_refresh_interval_seconds'])
            except (TypeError, ValueError):
                return Response(
                    {'map_refresh_interval_seconds': ['مقدار باید عدد صحیح برحسب ثانیه باشد.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not 5 <= interval <= 300:
                return Response(
                    {'map_refresh_interval_seconds': ['بازه مجاز بین ۵ تا ۳۰۰ ثانیه است.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            settings.map_refresh_interval_seconds = interval

        settings.save()
        return Response(self.serialize(settings))

    @staticmethod
    def serialize(settings):
        return {
            'map_provider': settings.map_provider,
            'map_refresh_interval_seconds': settings.map_refresh_interval_seconds,
            'updated_at': settings.updated_at,
        }
