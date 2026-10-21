from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("fleet", "0013_alter_devicemodel_protocol"),
    ]

    operations = [
        migrations.DeleteModel(name="UnknownGPSData"),
        migrations.DeleteModel(name="GPSTelemetry"),
    ]
