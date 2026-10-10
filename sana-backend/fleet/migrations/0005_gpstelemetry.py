from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("fleet", "0004_device_protocol_optional_model"),
        ("fleet", "0003_gt06position"),
    ]

    operations = [
        migrations.CreateModel(
            name="GPSTelemetry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("protocol", models.CharField(max_length=50)),
                ("gps_time", models.DateTimeField()),
                ("latitude", models.FloatField()),
                ("longitude", models.FloatField()),
                ("speed_kmh", models.FloatField(default=0)),
                ("raw_payload", models.BinaryField()),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="gps_telemetry", to="fleet.device")),
            ],
            options={
                "verbose_name": "داده تله‌متری GPS",
                "verbose_name_plural": "داده‌های تله‌متری GPS",
                "ordering": ["-gps_time", "-id"],
                "indexes": [models.Index(fields=["device", "gps_time"], name="fleet_gps_device_time_idx")],
            },
        ),
    ]
