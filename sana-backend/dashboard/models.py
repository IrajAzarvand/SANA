from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class SiteSettings(models.Model):
    """تنظیمات سراسری سایت؛ در عمل فقط یک رکورد با شناسه ثابت ۱ دارد."""

    MAP_PROVIDER_CHOICES = [
        ('leaflet-osm', 'OpenStreetMap'),
        ('neshan-leaflet', 'نشان'),
    ]

    map_provider = models.CharField(
        max_length=32,
        choices=MAP_PROVIDER_CHOICES,
        default='leaflet-osm',
        verbose_name='ارائه‌دهنده پیش‌فرض نقشه',
    )
    map_refresh_interval_seconds = models.PositiveSmallIntegerField(
        default=10,
        validators=[MinValueValidator(5), MaxValueValidator(300)],
        verbose_name='بازه به‌روزرسانی نقشه (ثانیه)',
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین تغییر')

    class Meta:
        verbose_name = 'تنظیمات سامانه'
        verbose_name_plural = 'تنظیمات سامانه'

    def save(self, *args, **kwargs):
        # رکورد singleton: تنظیمات سراسری همیشه شناسه ۱ دارد.
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return 'تنظیمات سراسری سانا'
