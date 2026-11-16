# Generated for per-user Traccar alert workflow state.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('fleet', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceAlertState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('traccar_event_id', models.CharField(max_length=64, verbose_name='شناسه رویداد Traccar')),
                ('event_type', models.CharField(max_length=64, verbose_name='نوع رویداد')),
                ('event_time', models.DateTimeField(verbose_name='زمان رویداد')),
                ('status', models.CharField(choices=[('new', 'جدید'), ('acknowledged', 'بررسی‌شده'), ('resolved', 'رفع‌شده')], default='new', max_length=20)),
                ('acknowledged_at', models.DateTimeField(blank=True, null=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='alert_states', to='fleet.device', verbose_name='دستگاه')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='device_alert_states', to=settings.AUTH_USER_MODEL, verbose_name='کاربر')),
            ],
            options={
                'verbose_name': 'وضعیت پیگیری هشدار',
                'verbose_name_plural': 'وضعیت‌های پیگیری هشدار',
                'ordering': ['-event_time', '-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='devicealertstate',
            constraint=models.UniqueConstraint(fields=('user', 'device', 'traccar_event_id'), name='fleet_alert_user_device_event_uniq'),
        ),
        migrations.AddIndex(
            model_name='devicealertstate',
            index=models.Index(fields=['user', 'status', 'event_time'], name='fleet_alert_user_status_idx'),
        ),
        migrations.AddIndex(
            model_name='devicealertstate',
            index=models.Index(fields=['device', 'event_type', 'event_time'], name='fleet_alert_device_type_idx'),
        ),
    ]
