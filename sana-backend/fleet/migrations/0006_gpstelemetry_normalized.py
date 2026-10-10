from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("fleet", "0005_gpstelemetry"),
    ]

    operations = [
        migrations.AlterField(
            model_name="gpstelemetry",
            name="latitude",
            field=models.DecimalField(
                blank=True, decimal_places=7, max_digits=10, null=True,
                verbose_name="عرض جغرافیایی",
            ),
        ),
        migrations.AlterField(
            model_name="gpstelemetry",
            name="longitude",
            field=models.DecimalField(
                blank=True, decimal_places=7, max_digits=10, null=True,
                verbose_name="طول جغرافیایی",
            ),
        ),
        migrations.AlterField(
            model_name="gpstelemetry",
            name="speed_kmh",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=7, null=True,
                verbose_name="سرعت (کیلومتر بر ساعت)",
            ),
        ),
        migrations.AddField(
            model_name="gpstelemetry",
            name="gps_valid",
            field=models.BooleanField(default=True, verbose_name="اعتبار GPS"),
        ),
        migrations.AddField(
            model_name="gpstelemetry",
            name="heading_deg",
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="جهت"),
        ),
        migrations.AddField(
            model_name="gpstelemetry",
            name="altitude_m",
            field=models.IntegerField(blank=True, null=True, verbose_name="ارتفاع (متر)"),
        ),
        migrations.AddField(
            model_name="gpstelemetry",
            name="satellites",
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="تعداد ماهواره"),
        ),
        migrations.AddField(
            model_name="gpstelemetry",
            name="attributes",
            field=models.JSONField(blank=True, default=dict, verbose_name="ویژگی‌های تله‌متری"),
        ),
        migrations.AddField(
            model_name="gpstelemetry",
            name="fingerprint",
            field=models.CharField(default="", max_length=64, verbose_name="اثر انگشت بسته"),
        ),
        migrations.RunSQL(
            sql="UPDATE fleet_gpstelemetry SET fingerprint = 'legacy-' || id::text WHERE fingerprint = '';",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AddIndex(
            model_name="gpstelemetry",
            index=models.Index(fields=["device", "received_at"], name="fleet_gps_device_received_idx"),
        ),
        migrations.AddConstraint(
            model_name="gpstelemetry",
            constraint=models.UniqueConstraint(
                fields=("device", "fingerprint"),
                name="fleet_gps_device_fingerprint_uniq",
            ),
        ),
    ]
