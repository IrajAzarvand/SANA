from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Device, DeviceOperation, DeviceReplacementRelation, DeviceLifecycleEvent, DeviceOwnershipHistory, DeviceCustomerAccessPeriod
from .lifecycle import record_device_lifecycle_event
from organizations.models import SubscriptionDevice


def _customer_kwargs(device=None, organization=None, user=None):
    organization = organization if organization is not None else (device.organization if device else None)
    user = user if user is not None else (device.owner_user if device else None)
    if organization:
        return {'organization': organization, 'user': None}
    if user:
        return {'organization': None, 'user': user}
    return {'organization': None, 'user': None}


def _close_customer_access(device, when=None):
    when = when or timezone.now()
    DeviceCustomerAccessPeriod.objects.filter(device=device, ended_at__isnull=True).update(ended_at=when)


def _open_customer_access(device, subscription=None, branch=None, organization=None, user=None, started_at=None, reason=''):
    customer = _customer_kwargs(device, organization, user)
    if not customer['organization'] and not customer['user']:
        return None
    current = DeviceCustomerAccessPeriod.objects.filter(device=device, ended_at__isnull=True).first()
    if current:
        same_customer = current.organization_id == getattr(customer['organization'], 'id', None) and current.user_id == getattr(customer['user'], 'id', None)
        branch_id = getattr(branch, 'id', None)
        if same_customer and current.branch_id != branch_id:
            _close_customer_access(device, started_at)
            current = None
        if current and same_customer:
            changed = []
            if subscription and current.subscription_id != subscription.id:
                current.subscription = subscription; changed.append('subscription')
            if branch and current.branch_id != branch.id:
                current.branch = branch; changed.append('branch')
            if changed: current.save(update_fields=changed)
            return current
        if current:
            _close_customer_access(device, started_at)
    return DeviceCustomerAccessPeriod.objects.create(device=device, subscription=subscription, branch=branch, started_at=started_at or timezone.now(), reason=reason, **customer)


def _close_ownership(device, when=None):
    when = when or timezone.now()
    DeviceOwnershipHistory.objects.filter(device=device, ended_at__isnull=True).update(ended_at=when)


def _open_ownership(device, organization=None, user=None, started_at=None, reason=''):
    customer = _customer_kwargs(device, organization, user)
    if not customer['organization'] and not customer['user']:
        return None
    current = DeviceOwnershipHistory.objects.filter(device=device, ended_at__isnull=True).first()
    same_customer = current and current.organization_id == getattr(customer['organization'], 'id', None) and current.owner_user_id == getattr(customer['user'], 'id', None)
    if same_customer:
        return current
    if current: _close_ownership(device, started_at)
    return DeviceOwnershipHistory.objects.create(device=device, started_at=started_at or timezone.now(), reason=reason, **customer)


def _close_active_link(device, operation):
    link = device.subscription_links.filter(
        unassigned_at__isnull=True
    ).select_related('subscription').first()
    if link:
        link.unassigned_at = timezone.now()
        link.save(update_fields=['unassigned_at'])
    return link


def _add_to_subscription(device, subscription, operation, start_date=None, end_date=None):
    if not subscription:
        raise ValidationError({'target_subscription': 'انتخاب قرارداد مقصد الزامی است'})
    start_date = start_date or subscription.start_date
    end_date = end_date or subscription.end_date
    if start_date > end_date:
        raise ValidationError({'target_subscription': 'بازه قرارداد مقصد نامعتبر است'})
    return SubscriptionDevice.objects.create(
        subscription=subscription,
        device=device,
        start_date=start_date,
        end_date=end_date,
    )


@transaction.atomic
def execute_device_operation(
    *,
    device,
    operation_type,
    performed_by,
    replacement_device=None,
    subscription=None,
    target_subscription=None,
    target_organization=None,
    target_user=None,
    target_branch=None,
    target_vehicle=None,
    replacement_type='',
    replacement_method='',
    outcome_action='',
    reason='',
    description='',
):
    device = Device.objects.select_for_update().get(pk=device.pk)
    if replacement_device:
        replacement_device = Device.objects.select_for_update().get(pk=replacement_device.pk)

    active_link = device.subscription_links.filter(
        unassigned_at__isnull=True
    ).select_related('subscription').first()
    subscription = subscription or (active_link.subscription if active_link else None)

    if replacement_device and replacement_device.pk == device.pk:
        raise ValidationError({'replacement_device': 'دستگاه جایگزین نمی‌تواند همان دستگاه قبلی باشد.'})

    old_status = device.management_status
    if device.organization_id or device.owner_user_id:
        _open_ownership(device, reason='customer_assignment')
        if active_link:
            _open_customer_access(device, subscription=active_link.subscription, branch=device.branch, reason='existing_relationship')

    operation = DeviceOperation.objects.create(
        operation_type=operation_type,
        device=device,
        replacement_device=replacement_device,
        subscription=subscription,
        target_subscription=target_subscription,
        target_organization=target_organization,
        target_user=target_user,
        target_branch=target_branch,
        target_vehicle=target_vehicle,
        replacement_type=replacement_type,
        replacement_method=replacement_method,
        outcome_action=outcome_action,
        reason=reason,
        description=description,
        old_status=old_status,
        performed_by=performed_by,
    )

    if operation_type == 'return_for_repair':
        if replacement_device:
            if replacement_type not in {'temporary_repair', 'permanent_replacement'}:
                raise ValidationError({'replacement_type': 'نوع جایگزینی را مشخص کنید'})
            if not replacement_method:
                raise ValidationError({'replacement_method': 'نحوه جایگزینی را مشخص کنید'})
            if replacement_type == 'temporary_repair' and replacement_method not in {
                'loaner', 'warranty', 'free_exchange', 'other'
            }:
                raise ValidationError({'replacement_method': 'برای جایگزینی موقت، نحوه انتخاب‌شده نامعتبر است'})
            if replacement_type == 'permanent_replacement' and replacement_method == 'loaner':
                raise ValidationError({'replacement_method': 'دستگاه دائمی نمی‌تواند امانی باشد'})
            if replacement_device.active_subscription_link:
                raise ValidationError({'replacement_device': 'دستگاه جایگزین در قرارداد دیگری فعال است.'})
            if replacement_device.management_status != 'warehouse' or not replacement_device.is_in_warehouse:
                raise ValidationError({'replacement_device': 'دستگاه جایگزین باید در انبار آزاد سانا باشد.'})

            old_vehicle = device.vehicle
            old_branch = device.branch
            old_org = device.organization or device.current_holder_organization
            old_user = device.owner_user or device.current_holder_user

            DeviceReplacementRelation.objects.create(
                source_device=device,
                replacement_device=replacement_device,
                replacement_type=replacement_type,
                description=description,
            )

            # تعمیر، مالکیت و اتصال قراردادی دستگاه اصلی را از بین نمی‌برد.
            device.vehicle = None
            device.branch = None
            device.current_holder_organization = None
            device.current_holder_user = None
            device.management_status = 'faulty'
            device.save()

            replacement_device.management_status = (
                'installed' if replacement_type == 'temporary_repair' else 'sold'
            )
            replacement_device.vehicle = old_vehicle
            replacement_device.branch = old_branch
            replacement_device.current_holder_organization = old_org
            replacement_device.current_holder_user = old_user
            if replacement_type == 'permanent_replacement':
                replacement_device.organization = old_org
                replacement_device.owner_user = old_user
            replacement_device.save()

            if replacement_type == 'permanent_replacement':
                _open_ownership(replacement_device, organization=old_org, user=old_user, reason='permanent_replacement')
            if subscription:
                _add_to_subscription(replacement_device, subscription, operation)
                _open_customer_access(replacement_device, subscription=subscription, branch=old_branch, organization=old_org, user=old_user, reason='replacement')

            record_device_lifecycle_event(
                device_operation=operation,
                device=device,
                event_type='sent_to_repair',
                performed_by=performed_by,
                subscription=subscription,
                organization=old_org,
                user=old_user,
                vehicle=old_vehicle,
                branch=old_branch,
                reason=reason or 'repair',
                description=description or 'دستگاه برای تعمیر به سانا بازگردانده شد.',
            )
            record_device_lifecycle_event(
                device_operation=operation,
                device=replacement_device,
                event_type='assigned_to_contract',
                performed_by=performed_by,
                subscription=subscription,
                organization=replacement_device.organization,
                user=replacement_device.owner_user,
                vehicle=replacement_device.vehicle,
                branch=replacement_device.branch,
                reason='replacement',
                description=f'به عنوان جایگزین دستگاه {device.imei} به قرارداد متصل شد.',
            )
        else:
            old_org = device.organization or device.current_holder_organization
            old_user = device.owner_user or device.current_holder_user
            old_vehicle = device.vehicle
            old_branch = device.branch

            device.vehicle = None
            device.branch = None
            device.current_holder_organization = None
            device.current_holder_user = None
            device.management_status = 'faulty'
            device.save()

            record_device_lifecycle_event(
                device_operation=operation,
                device=device,
                event_type='sent_to_repair',
                performed_by=performed_by,
                subscription=subscription,
                organization=old_org,
                user=old_user,
                vehicle=old_vehicle,
                branch=old_branch,
                reason=reason or 'repair',
                description=description or 'دستگاه برای تعمیر به سانا بازگردانده شد.',
            )

    elif operation_type == 'repaired':
        if device.management_status != 'faulty':
            raise ValidationError({
                'device': 'فقط دستگاهی که در وضعیت خرابی/تعمیر است قابل ثبت به عنوان تعمیرشده است.'
            })

        # پایان تعمیر فقط وضعیت فنی را تغییر می‌دهد.
        # تصمیم درباره مقصد بعدی در عملیات مستقل «تعیین تکلیف» انجام می‌شود.
        device.management_status = 'ready'
        device.vehicle = None
        device.branch = None
        device.current_holder_organization = None
        device.current_holder_user = None
        device.save()

        record_device_lifecycle_event(
            device_operation=operation,
            device=device,
            event_type='repaired',
            performed_by=performed_by,
            subscription=subscription,
            organization=device.organization,
            user=device.owner_user,
            vehicle=None,
            branch=None,
            reason=reason or 'repair',
            description=description or 'تعمیر دستگاه پایان یافت و دستگاه آماده تعیین تکلیف شد.',
        )

    elif operation_type in {'lost', 'stolen'}:
        if replacement_device:
            if replacement_type not in {'temporary_repair', 'permanent_replacement'}:
                raise ValidationError({'replacement_type': 'نوع جایگزینی را مشخص کنید'})
            if not replacement_method:
                raise ValidationError({'replacement_method': 'نحوه جایگزینی را مشخص کنید'})
            if replacement_type == 'temporary_repair' and replacement_method not in {
                'loaner', 'warranty', 'free_exchange', 'other'
            }:
                raise ValidationError({'replacement_method': 'برای جایگزینی موقت، نحوه انتخاب‌شده نامعتبر است'})
            if replacement_type == 'permanent_replacement' and replacement_method == 'loaner':
                raise ValidationError({'replacement_method': 'دستگاه دائمی نمی‌تواند امانی باشد'})
            if replacement_device.active_subscription_link or not replacement_device.is_in_warehouse:
                raise ValidationError({'replacement_device': 'دستگاه جایگزین باید در انبار آزاد سانا باشد.'})

        old_vehicle = device.vehicle
        old_branch = device.branch
        old_org = device.organization or device.current_holder_organization
        old_user = device.owner_user or device.current_holder_user

        # مفقودی/سرقت مالکیت و قرارداد را لغو نمی‌کند؛ فقط نصب فعلی را جدا می‌کند.
        device.vehicle = None
        device.current_holder_organization = old_org
        device.current_holder_user = old_user
        device.management_status = operation_type
        device.save()

        record_device_lifecycle_event(
            device_operation=operation,
            device=device,
            event_type=operation_type,
            performed_by=performed_by,
            subscription=subscription,
            organization=old_org,
            user=old_user,
            vehicle=old_vehicle,
            branch=old_branch,
            reason=reason,
            description=description or (
                'دستگاه مفقود شد.' if operation_type == 'lost' else 'سرقت دستگاه ثبت شد.'
            ),
        )

        if replacement_device:
            replacement_device.vehicle = old_vehicle
            replacement_device.branch = old_branch
            replacement_device.current_holder_organization = old_org
            replacement_device.current_holder_user = old_user
            replacement_device.management_status = (
                'installed' if replacement_type == 'temporary_repair' else 'sold'
            )
            if replacement_type == 'permanent_replacement':
                replacement_device.organization = old_org
                replacement_device.owner_user = old_user
            replacement_device.save()

            if subscription:
                _add_to_subscription(replacement_device, subscription, operation)

            DeviceReplacementRelation.objects.create(
                source_device=device,
                replacement_device=replacement_device,
                replacement_type=replacement_type,
                description=description or 'جایگزینی دستگاه مفقود/سرقت‌شده.',
            )
            record_device_lifecycle_event(
                device_operation=operation,
                device=replacement_device,
                event_type='assigned_to_contract',
                performed_by=performed_by,
                subscription=subscription,
                organization=replacement_device.organization,
                user=replacement_device.owner_user,
                vehicle=replacement_device.vehicle,
                branch=replacement_device.branch,
                reason='replacement',
                description=f'به عنوان جایگزین دستگاه {device.imei} به قرارداد متصل شد.',
            )

    elif operation_type == 'found':
        if device.management_status not in {'lost', 'stolen'}:
            raise ValidationError({
                'device': 'فقط دستگاه مفقود یا سرقت‌شده را می‌توان پیدا‌شده ثبت کرد.'
            })

        old_status = device.management_status
        device.management_status = 'ready'
        device.vehicle = None
        device.branch = None
        device.current_holder_organization = device.organization
        device.current_holder_user = device.owner_user
        device.save()

        record_device_lifecycle_event(
            device_operation=operation,
            device=device,
            event_type='found',
            performed_by=performed_by,
            subscription=subscription,
            organization=device.organization,
            user=device.owner_user,
            reason=reason or 'other',
            description=description or (
                f'دستگاه پس از وضعیت {old_status} پیدا شد و آماده تعیین تکلیف است.'
            ),
        )

    elif operation_type == 'disposition':
        if device.management_status != 'ready':
            raise ValidationError({
                'device': 'دستگاه باید ابتدا تعمیر یا پیدا شده و آماده تعیین تکلیف باشد.'
            })
        if not outcome_action:
            raise ValidationError({'outcome_action': 'تکلیف دستگاه را مشخص کنید'})

        previous_event = DeviceLifecycleEvent.objects.filter(
            device=device,
            event_type__in=['sent_to_repair', 'lost', 'stolen'],
        ).order_by('-event_date', '-id').first()
        previous_vehicle = previous_event.vehicle if previous_event else None
        previous_branch = previous_event.branch if previous_event else None
        previous_org = device.organization
        previous_user = device.owner_user

        if outcome_action == 'return_customer_same_vehicle':
            target = previous_vehicle
            if not target:
                raise ValidationError({
                    'outcome_action': 'خودروی قبلی برای بازگشت مشخص نیست؛ خودروی مقصد را انتخاب کنید.'
                })
            if Device.objects.filter(vehicle=target).exclude(pk=device.pk).exclude(
                management_status__in=['faulty', 'lost', 'stolen', 'retired', 'disposed']
            ).exists():
                raise ValidationError({
                    'outcome_action': 'خودروی قبلی هنوز دستگاه دیگری دارد؛ ابتدا تکلیف آن دستگاه را مشخص کنید.'
                })
            device.vehicle = target
            device.branch = previous_branch or target.branch
            device.current_holder_organization = previous_org
            device.current_holder_user = previous_user
            device.management_status = 'installed'

        elif outcome_action == 'return_customer_no_vehicle':
            device.vehicle = None
            device.branch = None
            device.current_holder_organization = previous_org
            device.current_holder_user = previous_user
            device.management_status = 'sold'

        elif outcome_action == 'sana_warehouse':
            device.vehicle = None
            device.branch = None
            device.current_holder_organization = None
            device.current_holder_user = None
            device.management_status = 'warehouse'

        elif outcome_action == 'customer_spare':
            device.vehicle = None
            device.branch = None
            device.current_holder_organization = previous_org
            device.current_holder_user = previous_user
            device.management_status = 'sold'

        elif outcome_action == 'install_other_vehicle':
            if not target_vehicle:
                raise ValidationError({
                    'target_vehicle': 'برای نصب روی خودروی دیگر، خودروی مقصد را مشخص کنید'
                })
            if previous_org and target_vehicle.organization_id != previous_org.id:
                raise ValidationError({
                    'target_vehicle': 'خودروی مقصد باید متعلق به همان مشتری دستگاه باشد'
                })
            if Device.objects.filter(vehicle=target_vehicle).exclude(pk=device.pk).exclude(
                management_status__in=['faulty', 'lost', 'stolen', 'retired', 'disposed']
            ).exists():
                raise ValidationError({'target_vehicle': 'خودروی مقصد در حال حاضر دستگاه دیگری دارد.'})
            device.vehicle = target_vehicle
            device.branch = target_vehicle.branch
            device.current_holder_organization = previous_org
            device.current_holder_user = previous_user
            device.management_status = 'installed'

        elif outcome_action == 'transfer_customer':
            if not target_organization and not target_user:
                raise ValidationError({'target_organization': 'مالک مقصد را مشخص کنید'})
            device.organization = target_organization
            device.owner_user = target_user
            device.current_holder_organization = target_organization
            device.current_holder_user = target_user
            device.vehicle = target_vehicle
            device.branch = target_vehicle.branch if target_vehicle else target_branch
            device.management_status = 'sold'

        elif outcome_action == 'retire':
            device.vehicle = None
            device.branch = None
            device.current_holder_organization = previous_org
            device.current_holder_user = previous_user
            device.management_status = 'retired'

        elif outcome_action == 'dispose':
            device.organization = None
            device.owner_user = None
            device.current_holder_organization = None
            device.current_holder_user = None
            device.vehicle = None
            device.branch = None
            device.management_status = 'disposed'

        elif outcome_action == 'other':
            device.vehicle = None
            device.branch = None
            device.management_status = 'ready'

        device.save()

        if outcome_action == 'transfer_customer':
            _close_active_link(device, operation)
            if target_subscription:
                _add_to_subscription(device, target_subscription, operation)
        elif outcome_action == 'dispose':
            _close_active_link(device, operation)

        disposition_labels = {
            'return_customer_same_vehicle': 'به مشتری بازگشت و روی خودرو نصب شد',
            'return_customer_no_vehicle': 'به مشتری بازگشت و فعلاً نصب نشد',
            'sana_warehouse': 'به انبار سانا رفت',
            'customer_spare': 'به عنوان دستگاه یدکی مشتری نگهداری شد',
            'install_other_vehicle': 'روی خودروی دیگر نصب شد',
            'transfer_customer': 'به مشتری دیگر منتقل شد',
            'retire': 'بازنشسته شد',
            'dispose': 'امحاء شد',
            'other': 'طبق توضیحات تکمیلی تعیین شد',
        }
        record_device_lifecycle_event(
            device_operation=operation,
            device=device,
            event_type='disposition',
            performed_by=performed_by,
            subscription=target_subscription or subscription,
            organization=device.organization,
            user=device.owner_user,
            vehicle=device.vehicle,
            branch=device.branch,
            reason=reason or 'other',
            description=description or disposition_labels[outcome_action],
        )

    elif operation_type == 'transfer_customer':
        if not target_organization and not target_user:
            raise ValidationError({'target_organization': 'مالک مقصد را مشخص کنید'})
        _close_active_link(device, operation)
        _close_customer_access(device)
        _close_ownership(device)
        device.organization = target_organization
        device.owner_user = target_user
        device.current_holder_organization = target_organization
        device.current_holder_user = target_user
        device.branch = None
        device.vehicle = None
        device.management_status = 'sold'
        device.save()
        if target_subscription:
            _add_to_subscription(device, target_subscription, operation)
        _open_ownership(device, organization=target_organization, user=target_user, reason='transfer_customer')
        _open_customer_access(device, subscription=target_subscription, branch=target_branch, organization=target_organization, user=target_user, reason='transfer_customer')
        record_device_lifecycle_event(
            device_operation=operation,
            device=device,
            event_type='transferred',
            performed_by=performed_by,
            subscription=target_subscription or subscription,
            organization=target_organization,
            user=target_user,
            reason=reason,
            description=description,
        )

    elif operation_type == 'transfer_branch':
        if not target_branch:
            raise ValidationError({'target_branch': 'شعبه مقصد را مشخص کنید'})
        device.branch = target_branch
        device.save(update_fields=['branch', 'updated_at'])
        _open_customer_access(device, subscription=subscription, branch=target_branch)
        record_device_lifecycle_event(
            device_operation=operation,
            device=device,
            event_type='transferred',
            performed_by=performed_by,
            subscription=subscription,
            organization=device.organization,
            user=device.owner_user,
            vehicle=device.vehicle,
            branch=target_branch,
            reason=reason,
            description=description,
        )

    elif operation_type == 'transfer_vehicle':
        if not target_vehicle:
            raise ValidationError({'target_vehicle': 'خودرو مقصد را مشخص کنید'})
        if target_vehicle.organization_id != device.organization_id and device.organization_id:
            raise ValidationError({
                'target_vehicle': 'خودرو مقصد باید متعلق به همان مشتری دستگاه باشد'
            })
        if Device.objects.filter(vehicle=target_vehicle).exclude(pk=device.pk).exclude(
            management_status__in=['faulty', 'lost', 'stolen', 'retired', 'disposed']
        ).exists():
            raise ValidationError({'target_vehicle': 'خودروی مقصد در حال حاضر دستگاه دیگری دارد.'})
        old_vehicle = device.vehicle
        device.vehicle = target_vehicle
        device.branch = target_vehicle.branch
        device.save(update_fields=['vehicle', 'branch', 'updated_at'])
        _open_customer_access(device, subscription=subscription, branch=target_vehicle.branch)
        record_device_lifecycle_event(
            device_operation=operation,
            device=device,
            event_type='transferred',
            performed_by=performed_by,
            subscription=subscription,
            organization=device.organization,
            user=device.owner_user,
            vehicle=target_vehicle,
            branch=target_vehicle.branch,
            reason=reason,
            description=description or (
                f'انتقال از خودرو {old_vehicle.plate if old_vehicle else "بدون خودرو"} انجام شد.'
            ),
        )

    elif operation_type == 'retire':
        device.management_status = 'retired'
        device.vehicle = None
        device.branch = None
        device.save(update_fields=['management_status', 'vehicle', 'branch', 'updated_at'])
        record_device_lifecycle_event(
            device_operation=operation,
            device=device,
            event_type='retired',
            performed_by=performed_by,
            subscription=subscription,
            organization=device.organization,
            user=device.owner_user,
            reason=reason,
            description=description,
        )

    elif operation_type == 'dispose':
        if device.management_status != 'retired':
            raise ValidationError({'device': 'برای امحاء ابتدا دستگاه باید بازنشسته شود.'})
        _close_active_link(device, operation)
        device.management_status = 'disposed'
        device.vehicle = None
        device.branch = None
        device.save(update_fields=['management_status', 'vehicle', 'branch', 'updated_at'])
        record_device_lifecycle_event(
            device_operation=operation,
            device=device,
            event_type='disposed',
            performed_by=performed_by,
            subscription=subscription,
            organization=device.organization,
            user=device.owner_user,
            reason=reason,
            description=description,
        )
    else:
        raise ValidationError({'operation_type': 'نوع عملیات پشتیبانی نمی‌شود'})

    operation.new_status = device.management_status
    operation.save(update_fields=['new_status'])
    return operation
