# Generated for role-aware notification read state.
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_user_session'),
    ]

    operations = [
        migrations.CreateModel(
            name='NotificationReadState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_key', models.CharField(max_length=200, verbose_name='شناسه رویداد')),
                ('read_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='زمان خواندن')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notification_read_states', to=settings.AUTH_USER_MODEL, verbose_name='کاربر')),
            ],
            options={
                'verbose_name': 'وضعیت خواندن اعلان',
                'verbose_name_plural': 'وضعیت‌های خواندن اعلان',
            },
        ),
        migrations.AddConstraint(
            model_name='notificationreadstate',
            constraint=models.UniqueConstraint(fields=('user', 'event_key'), name='accounts_notif_user_event_uniq'),
        ),
        migrations.AddIndex(
            model_name='notificationreadstate',
            index=models.Index(fields=['user', 'read_at'], name='accounts_notif_user_read_idx'),
        ),
    ]
