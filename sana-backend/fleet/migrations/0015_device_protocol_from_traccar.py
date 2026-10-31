from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("fleet", "0014_remove_duplicate_gps_storage"),
    ]

    operations = [
        migrations.AlterField(
            model_name="device",
            name="protocol",
            field=models.CharField(
                blank=True,
                default="",
                help_text="از فیلد protocol آخرین موقعیت دریافت‌شده از Traccar به‌روزرسانی می‌شود.",
                max_length=50,
                verbose_name="پروتکل گزارش‌شده توسط Traccar",
            ),
        ),
    ]
