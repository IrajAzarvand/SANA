from calendar import monthrange
from datetime import date
from decimal import Decimal

from rest_framework.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from .models import (
    SubscriptionInstallment,
    SubscriptionInstallmentPlan,
    SubscriptionPaymentAllocation,
)


def add_months(value: date, months: int) -> date:
    """Add calendar months while clamping month-end dates safely."""
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def create_installment_plan(subscription, data, created_by=None):
    """Create a new schedule version; never overwrite a previous version."""
    mode = data.get('calculation_mode', 'equal')
    count = int(data.get('installment_count') or 0)
    interval = int(data.get('interval_months') or 0)
    scheduled_amount = Decimal(str(data.get('scheduled_amount', 0)))

    if count < 1 or count > 120:
        raise ValidationError({'installment_count': 'تعداد اقساط باید بین ۱ تا ۱۲۰ باشد'})
    if interval < 1 or interval > 120:
        raise ValidationError({'interval_months': 'فاصله اقساط باید بین ۱ تا ۱۲۰ ماه باشد'})
    if scheduled_amount <= 0:
        raise ValidationError({'scheduled_amount': 'مبلغ اقساط باید بیشتر از صفر باشد'})

    custom_amounts = data.get('custom_amounts') or []
    if mode == 'equal':
        base, remainder = divmod(int(scheduled_amount), count)
        amounts = [Decimal(base) for _ in range(count)]
        amounts[-1] += Decimal(remainder)
    elif mode == 'custom':
        if len(custom_amounts) != count:
            raise ValidationError({'custom_amounts': 'تعداد مبالغ باید با تعداد اقساط برابر باشد'})
        amounts = [Decimal(str(value)) for value in custom_amounts]
        if any(value <= 0 for value in amounts):
            raise ValidationError({'custom_amounts': 'مبلغ هر قسط باید بیشتر از صفر باشد'})
        if sum(amounts) != scheduled_amount:
            raise ValidationError({'custom_amounts': 'مجموع مبالغ اقساط باید دقیقاً برابر مبلغ قابل تقسیط باشد'})
    else:
        raise ValidationError({'calculation_mode': 'روش محاسبه اقساط نامعتبر است'})

    with transaction.atomic():
        subscription.__class__.objects.select_for_update().get(pk=subscription.pk)
        previous = SubscriptionInstallmentPlan.objects.filter(
            subscription=subscription, status='active',
        ).first()
        version = (
            SubscriptionInstallmentPlan.objects.filter(subscription=subscription)
            .order_by('-version').values_list('version', flat=True).first() or 0
        ) + 1
        if previous:
            previous.status = 'superseded'
            previous.save(update_fields=['status'])

        plan = SubscriptionInstallmentPlan.objects.create(
            subscription=subscription,
            version=version,
            scheduled_amount=scheduled_amount,
            installment_count=count,
            interval_months=interval,
            calculation_mode=mode,
            surplus_policy=data.get('surplus_policy', 'credit'),
            created_by=created_by,
        )
        SubscriptionInstallment.objects.bulk_create([
            SubscriptionInstallment(
                plan=plan,
                number=index,
                amount=amount,
                due_date=add_months(subscription.start_date, interval * index),
            )
            for index, amount in enumerate(amounts, start=1)
        ])
    return plan


def installment_allocated_amount(installment):
    return installment.allocations.aggregate(total=Sum('amount'))['total'] or Decimal('0')


def installment_remaining_amount(installment):
    return max(Decimal(installment.amount) - installment_allocated_amount(installment), Decimal('0'))


def allocate_payment(payment, mode='automatic', allocations=None, allocation_type='installment'):
    """Allocate a receipt to installments or leave its remainder as customer credit."""
    from .models import SubscriptionPayment

    with transaction.atomic():
        locked_payment = SubscriptionPayment.objects.select_for_update().get(pk=payment.pk)
        already_allocated = locked_payment.allocations.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        available = Decimal(locked_payment.amount) - already_allocated
        if available < 0:
            raise ValidationError('مجموع تخصیص‌ها از مبلغ دریافتی بیشتر است')

        if allocation_type == 'contract_advance':
            if mode != 'automatic' or allocations:
                raise ValidationError('پیش‌پرداخت قرارداد به‌صورت مستقیم ثبت می‌شود')
            if available:
                SubscriptionPaymentAllocation.objects.create(
                    payment=locked_payment,
                    installment=None,
                    allocation_type='contract_advance',
                    amount=available,
                )
            return

        if mode == 'manual':
            if not allocations:
                raise ValidationError({'allocations': 'برای تخصیص دستی حداقل یک قسط انتخاب کنید'})
            requested_total = Decimal('0')
            for item in allocations:
                installment = SubscriptionInstallment.objects.select_for_update().select_related(
                    'plan__subscription'
                ).filter(
                    pk=item.get('installment_id'),
                    plan__subscription_id=locked_payment.subscription_id,
                    plan__status='active',
                    status='active',
                ).first()
                if not installment:
                    raise ValidationError({'allocations': 'یکی از اقساط انتخاب‌شده معتبر یا فعال نیست'})
                amount = Decimal(str(item.get('amount', 0)))
                remaining = installment_remaining_amount(installment)
                if amount <= 0 or amount > remaining:
                    raise ValidationError({'allocations': f'مبلغ تخصیص قسط {installment.number} نامعتبر است'})
                requested_total += amount
                if requested_total > available:
                    raise ValidationError({'allocations': 'مجموع تخصیص‌ها از مبلغ آزاد دریافتی بیشتر است'})
                SubscriptionPaymentAllocation.objects.create(
                    payment=locked_payment,
                    installment=installment,
                    allocation_type='installment',
                    amount=amount,
                )
            return

        if mode != 'automatic':
            raise ValidationError({'allocation_mode': 'روش تخصیص نامعتبر است'})

        if available <= 0:
            return
        active_plan = SubscriptionInstallmentPlan.objects.filter(
            subscription_id=locked_payment.subscription_id,
            status='active',
        ).first()
        if not active_plan:
            return

        installments = SubscriptionInstallment.objects.select_for_update().filter(
            plan=active_plan,
            status='active',
        ).order_by('due_date', 'number')
        due_installments = installments.filter(due_date__lte=locked_payment.payment_date)
        for installment in due_installments:
            remaining = installment_remaining_amount(installment)
            if remaining <= 0:
                continue
            amount = min(available, remaining)
            SubscriptionPaymentAllocation.objects.create(
                payment=locked_payment,
                installment=installment,
                allocation_type='installment',
                amount=amount,
            )
            available -= amount
            if available <= 0:
                break

        # Future installments are touched only when the plan explicitly allows it.
        if available > 0 and active_plan.surplus_policy == 'future':
            for installment in installments.filter(due_date__gt=locked_payment.payment_date):
                remaining = installment_remaining_amount(installment)
                if remaining <= 0:
                    continue
                amount = min(available, remaining)
                SubscriptionPaymentAllocation.objects.create(
                    payment=locked_payment,
                    installment=installment,
                    allocation_type='installment',
                    amount=amount,
                )
                available -= amount
                if available <= 0:
                    break
        # Any remaining amount is intentionally left unallocated as customer credit.
