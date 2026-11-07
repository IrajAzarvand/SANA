# Generated for the versioned contract installment ledger.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('organizations', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SubscriptionInstallmentPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.PositiveIntegerField(verbose_name='نسخه برنامه')),
                ('scheduled_amount', models.DecimalField(decimal_places=0, max_digits=15, verbose_name='مبلغ اقساط (ریال)')),
                ('installment_count', models.PositiveSmallIntegerField(verbose_name='تعداد اقساط')),
                ('interval_months', models.PositiveSmallIntegerField(verbose_name='فاصله اقساط (ماه)')),
                ('calculation_mode', models.CharField(choices=[('equal', 'اقساط مساوی'), ('custom', 'مبالغ دلخواه')], max_length=10, verbose_name='روش محاسبه')),
                ('surplus_policy', models.CharField(choices=[('credit', 'ثبت به‌عنوان اعتبار مشتری'), ('future', 'تخصیص به اقساط آینده')], default='credit', max_length=10, verbose_name='نحوه مازاد دریافتی')),
                ('status', models.CharField(choices=[('active', 'فعال'), ('superseded', 'جایگزین‌شده')], default='active', max_length=12, verbose_name='وضعیت')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_installment_plans', to=settings.AUTH_USER_MODEL, verbose_name='ایجادکننده')),
                ('subscription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='installment_plans', to='organizations.subscription', verbose_name='قرارداد')),
            ],
            options={
                'verbose_name': 'برنامه اقساط',
                'verbose_name_plural': 'برنامه‌های اقساط',
                'ordering': ['-version'],
            },
        ),
        migrations.CreateModel(
            name='SubscriptionInstallment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.PositiveSmallIntegerField(verbose_name='شماره قسط')),
                ('amount', models.DecimalField(decimal_places=0, max_digits=15, verbose_name='مبلغ قسط (ریال)')),
                ('due_date', models.DateField(verbose_name='سررسید')),
                ('status', models.CharField(choices=[('active', 'فعال'), ('superseded', 'جایگزین‌شده')], default='active', max_length=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='installments', to='organizations.subscriptioninstallmentplan', verbose_name='برنامه اقساط')),
            ],
            options={
                'verbose_name': 'قسط',
                'verbose_name_plural': 'اقساط',
                'ordering': ['due_date', 'number'],
            },
        ),
        migrations.CreateModel(
            name='SubscriptionPaymentAllocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('allocation_type', models.CharField(choices=[('installment', 'قسط'), ('contract_advance', 'پیش‌پرداخت قرارداد')], max_length=20, verbose_name='نوع تخصیص')),
                ('amount', models.DecimalField(decimal_places=0, max_digits=15, verbose_name='مبلغ تخصیص (ریال)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('installment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='allocations', to='organizations.subscriptioninstallment', verbose_name='قسط')),
                ('payment', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='allocations', to='organizations.subscriptionpayment', verbose_name='دریافتی')),
            ],
            options={
                'verbose_name': 'تخصیص دریافتی',
                'verbose_name_plural': 'تخصیص‌های دریافتی',
                'ordering': ['created_at', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='subscriptioninstallmentplan',
            constraint=models.UniqueConstraint(fields=('subscription', 'version'), name='org_installment_plan_version_uniq'),
        ),
        migrations.AddConstraint(
            model_name='subscriptioninstallmentplan',
            constraint=models.UniqueConstraint(condition=models.Q(status='active'), fields=('subscription',), name='org_one_active_installment_plan'),
        ),
        migrations.AddConstraint(
            model_name='subscriptioninstallment',
            constraint=models.UniqueConstraint(fields=('plan', 'number'), name='org_installment_plan_number_uniq'),
        ),
        migrations.AddConstraint(
            model_name='subscriptioninstallment',
            constraint=models.CheckConstraint(condition=models.Q(amount__gt=0), name='org_installment_amount_positive'),
        ),
        migrations.AddConstraint(
            model_name='subscriptionpaymentallocation',
            constraint=models.CheckConstraint(condition=models.Q(amount__gt=0), name='org_payment_allocation_positive'),
        ),
        migrations.AddConstraint(
            model_name='subscriptionpaymentallocation',
            constraint=models.CheckConstraint(
                condition=models.Q(models.Q(('allocation_type', 'installment'), ('installment__isnull', False)), models.Q(('allocation_type', 'contract_advance'), ('installment__isnull', True)), _connector='OR'),
                name='org_allocation_type_installment_consistent',
            ),
        ),
        migrations.AddConstraint(
            model_name='subscriptionpaymentallocation',
            constraint=models.UniqueConstraint(condition=models.Q(installment__isnull=False), fields=('payment', 'installment'), name='org_payment_installment_allocation_uniq'),
        ),
    ]
