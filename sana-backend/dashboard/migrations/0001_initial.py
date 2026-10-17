from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='SiteSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('map_provider', models.CharField(
                    choices=[('leaflet-osm', 'OpenStreetMap'), ('neshan-leaflet', 'نشان')],
                    default='leaflet-osm',
                    max_length=32,
                    verbose_name='ارائه‌دهنده پیش‌فرض نقشه',
                )),
                ('map_refresh_interval_seconds', models.PositiveSmallIntegerField(
                    default=10,
                    validators=[django.core.validators.MinValueValidator(5), django.core.validators.MaxValueValidator(300)],
                    verbose_name='بازه به‌روزرسانی نقشه (ثانیه)',
                )),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='آخرین تغییر')),
            ],
            options={
                'verbose_name': 'تنظیمات سامانه',
                'verbose_name_plural': 'تنظیمات سامانه',
            },
        ),
    ]
