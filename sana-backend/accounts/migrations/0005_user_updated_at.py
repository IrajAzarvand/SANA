import django.utils.timezone
from django.db import migrations, models
from django.db.models import F


def preserve_existing_join_dates(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    User.objects.update(updated_at=F('date_joined'))


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_notification_read_state'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now, verbose_name='آخرین به‌روزرسانی'),
            preserve_default=False,
        ),
        migrations.RunPython(preserve_existing_join_dates, migrations.RunPython.noop),
    ]
