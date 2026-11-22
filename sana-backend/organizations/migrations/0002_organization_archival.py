from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('organizations', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='organization',
            name='status',
            field=models.CharField(
                choices=[('active', 'فعال'), ('inactive', 'غیرفعال'), ('suspended', 'تعلیق‌شده'), ('archived', 'بایگانی‌شده')],
                default='active', max_length=20, verbose_name='وضعیت',
            ),
        ),
        migrations.AddField(
            model_name='organization',
            name='archived_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='زمان بایگانی'),
        ),
        migrations.AddField(
            model_name='organization',
            name='archived_from_status',
            field=models.CharField(blank=True, max_length=20, verbose_name='وضعیت پیش از بایگانی'),
        ),
        migrations.AddField(
            model_name='organization',
            name='archived_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='archived_organizations',
                to=settings.AUTH_USER_MODEL,
                verbose_name='بایگانی‌کننده',
            ),
        ),
    ]
