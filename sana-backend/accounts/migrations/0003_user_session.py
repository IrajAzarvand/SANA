# Generated for server-side authentication session tracking.
import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserSession',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='زمان ورود')),
                ('last_activity_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='آخرین فعالیت')),
                ('expires_at', models.DateTimeField(verbose_name='انقضای نشست')),
                ('revoked_at', models.DateTimeField(blank=True, null=True, verbose_name='زمان ابطال')),
                ('current_refresh_jti', models.CharField(blank=True, max_length=255, verbose_name='شناسه Refresh فعلی')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP ورود')),
                ('user_agent', models.CharField(blank=True, max_length=512, verbose_name='مرورگر/دستگاه')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='auth_sessions', to=settings.AUTH_USER_MODEL, verbose_name='کاربر')),
            ],
            options={
                'verbose_name': 'نشست ورود',
                'verbose_name_plural': 'نشست‌های ورود',
                'indexes': [
                    models.Index(fields=['user', 'revoked_at'], name='accounts_sess_user_rev_idx'),
                    models.Index(fields=['expires_at'], name='accounts_sess_expires_idx'),
                ],
            },
        ),
    ]
