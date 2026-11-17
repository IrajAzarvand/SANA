# Generated for per-user personal alert filtering.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('fleet', '0003_device_alert_state'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PersonalAlertPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('disabled_event_types', models.JSONField(blank=True, default=list, verbose_name='انواع هشدار غیرفعال')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='personal_alert_preference', to=settings.AUTH_USER_MODEL, verbose_name='کاربر')),
            ],
            options={
                'verbose_name': 'تنظیمات هشدار مشتری شخصی',
                'verbose_name_plural': 'تنظیمات هشدار مشتریان شخصی',
            },
        ),
    ]
