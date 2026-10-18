import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("decoder_discovery", "0001_initial"),
        ("fleet", "0009_unknowngpsdata"),
    ]

    operations = [
        migrations.AddField(
            model_name="discoverycase",
            name="queue_session_id",
            field=models.UUIDField(blank=True, db_index=True, null=True, unique=True),
        ),
        migrations.CreateModel(
            name="DiscoverySample",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("payload_sha256", models.CharField(db_index=True, max_length=64)),
                ("payload_size_bytes", models.PositiveIntegerField(default=0)),
                ("features", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("case", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="samples", to="decoder_discovery.discoverycase")),
                ("queue_row", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="discovery_sample", to="fleet.unknowngpsdata")),
            ],
            options={
                "ordering": ("queue_row_id",),
            },
        ),
        migrations.AddIndex(
            model_name="discoverysample",
            index=models.Index(fields=["case", "queue_row"], name="decoder_sample_case_queue"),
        ),
    ]
