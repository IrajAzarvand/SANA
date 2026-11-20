# Remove the obsolete business-notification read-state table; status now lives in fleet.DeviceAlertState.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_user_updated_at'),
    ]

    operations = [
        migrations.DeleteModel(
            name='NotificationReadState',
        ),
    ]
