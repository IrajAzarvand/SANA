# Generated for durable storage of unknown GPS protocol data.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0008_gpstelemetry_fleet_gps_device_received_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='UnknownGPSData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_id', models.UUIDField(verbose_name='شناسه نشست دریافت')),
                ('transport', models.CharField(max_length=8, verbose_name='نوع ارتباط')),
                ('remote_address', models.CharField(max_length=255, verbose_name='آدرس فرستنده')),
                ('raw_payload', models.BinaryField(verbose_name='داده خام')),
                ('identifier_candidate', models.CharField(blank=True, default='', max_length=20, verbose_name='شناسه احتمالی دستگاه')),
                ('status', models.CharField(choices=[('pending', 'در انتظار شناسایی'), ('matched', 'شناسه شناسایی شد'), ('failed', 'نیازمند بررسی بیشتر')], default='pending', max_length=16, verbose_name='وضعیت بررسی')),
                ('received_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='زمان دریافت')),
            ],
            options={
                'verbose_name': 'داده GPS ناشناخته',
                'verbose_name_plural': 'داده‌های GPS ناشناخته',
                'ordering': ['id'],
            },
        ),
        migrations.AddIndex(
            model_name='unknowngpsdata',
            index=models.Index(fields=['session_id', 'id'], name='fleet_unknown_session_idx'),
        ),
        migrations.AddIndex(
            model_name='unknowngpsdata',
            index=models.Index(fields=['status', 'id'], name='fleet_unknown_status_id_idx'),
        ),
    ]
