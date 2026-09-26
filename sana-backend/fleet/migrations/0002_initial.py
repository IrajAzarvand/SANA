from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('fleet','0001_initial'),('organizations','0001_initial'),('accounts','0001_initial')]
    operations = [
        migrations.AddField(model_name='vehicletype', name='organization', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='vehicle_types', to='organizations.organization', verbose_name='سازمان')),
        migrations.AddField(model_name='vehicle', name='organization', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='vehicles', to='organizations.organization', verbose_name='سازمان')),
        migrations.AddField(model_name='vehicle', name='owner_user', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='personal_vehicles', to='accounts.user', verbose_name='مالک شخصی')),
        migrations.AddField(model_name='vehicle', name='branch', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='vehicles', to='organizations.branch', verbose_name='شعبه')),
        migrations.AddField(model_name='device', name='organization', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='devices', to='organizations.organization', verbose_name='سازمان')),
        migrations.AddField(model_name='device', name='owner_user', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='personal_devices', to='accounts.user', verbose_name='مالک شخصی')),
        migrations.AddField(model_name='device', name='branch', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='devices', to='organizations.branch', verbose_name='شعبه')),
        migrations.AddField(model_name='driver', name='organization', field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='drivers', to='organizations.organization', verbose_name='سازمان')),
        migrations.AddField(model_name='driver', name='branch', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='drivers', to='organizations.branch', verbose_name='شعبه')),
    ]