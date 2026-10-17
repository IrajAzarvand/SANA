from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SiteSettings


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
