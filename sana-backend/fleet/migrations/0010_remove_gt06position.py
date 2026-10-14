# Remove the obsolete protocol-specific GT06 position table.
#
# GT06 telemetry is persisted through the shared gps.raw_packet,
# gps.location_history, and gps.current_state tables.
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("fleet", "0009_unknowngpsdata"),
        ("fleet", "0003_gt06position"),
    ]

    operations = [
        migrations.DeleteModel(
            name="GT06Position",
        ),
    ]
