# Generated for GT06 GPS position persistence.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("fleet", "0002_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="GT06Position",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("gps_time", models.DateTimeField(verbose_name="زمان GPS")),
                ("latitude", models.FloatField(verbose_name="عرض جغرافیایی")),
                ("longitude", models.FloatField(verbose_name="طول جغرافیایی")),
                ("speed_kmh", models.PositiveSmallIntegerField(default=0, verbose_name="سرعت (کیلومتر بر ساعت)")),
                ("course", models.PositiveSmallIntegerField(default=0, verbose_name="جهت حرکت")),
                ("satellites", models.PositiveSmallIntegerField(default=0, verbose_name="تعداد ماهواره")),
                ("raw_frame", models.BinaryField(verbose_name="بسته خام")),
                ("received_at", models.DateTimeField(auto_now_add=True, verbose_name="زمان دریافت")),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="gt06_positions", to="fleet.device", verbose_name="دستگاه")),
            ],
            options={
                "verbose_name": "موقعیت GT06",
                "verbose_name_plural": "موقعیت‌های GT06",
                "ordering": ["-gps_time", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="gt06position",
            index=models.Index(fields=["device", "gps_time"], name="fleet_gt06_device_time_idx"),
        ),
    ]
