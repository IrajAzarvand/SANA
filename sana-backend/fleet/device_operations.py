from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Device, DeviceOperation, DeviceReplacementRelation, DeviceLifecycleEvent
from .lifecycle import record_device_lifecycle_event
from organizations.models import SubscriptionDevice


def _close_active_link(device, operation):
    link = device.subscription_links.filter(unassigned_at__isnull=True).select_related('subscription').first()
    if link:
        link.unassigned_at = timezone.now()
        # DeviceOperation is a separate audit model from SubscriptionOperation.
        # SubscriptionDevice keeps its legacy SubscriptionOperation links nullable;
        # the DeviceOperation itself already records this operation and subscription.
        link.save(update_fields=['unassigned_at'])
    return link


def _add_to_subscription(device, subscription, operation, start_date=None, end_date=None):
    if not subscription:
        raise ValidationError({'target_subscription': 'انتخاب قرارداد مقصد الزامی است'})
    start_date = start_date or subscription.start_date
    end_date = end_date or subscription.end_date
    if start_date > end_date:
        raise ValidationError({'target_subscription': 'بازه قرارداد مقصد نامعتبر است'})
    link = SubscriptionDevice.objects.create(
        subscription=subscription,
        device=device,
        start_date=start_date,
        end_date=end_date,
    )
    return link


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
    repair_return_action='',
    reason='',
    description='',
):
    device = Device.objects.select_for_update().get(pk=device.pk)
    if replacement_device:
        replacement_device = Device.objects.select_for_update().get(pk=replacement_device.pk)

    active_link = device.subscription_links.filter(unassigned_at__isnull=True).select_related('subscription').first()
    subscription = subscription or (active_link.subscription if active_link else None)

    if replacement_device and replacement_device.pk == device.pk:
        raise ValidationError({'replacement_device': 'دستگاه جایگزین نمی‌تواند همان دستگاه قبلی باشد.'})

    old_status = device.management_status
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
        repair_return_action=repair_return_action,
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
            if replacement_type == 'temporary_repair' and replacement_method not in {'loaner', 'warranty', 'free_exchange', 'other'}:
                raise ValidationError({'replacement_method': 'برای جایگزینی موقت، نحوه انتخاب‌شده نامعتبر است'})
            if replacement_type == 'permanent_replacement' and replacement_method == 'loaner':
                raise ValidationError({'replacement_method': 'دستگاه دائمی نمی‌تواند امانی باشد'})
            if replacement_device.active_subscription_link:
                raise ValidationError({'replacement_device': 'دستگاه جایگزین در قرارداد دیگری فعال است.'})
            if replacement_device.management_status != 'warehouse' or not replacement_device.is_in_warehouse:
                raise ValidationError({'replacement_device': 'دستگاه جایگزین باید در انبار آزاد سانا باشد.'})

            relation = DeviceReplacementRelation.objects.create(
                source_device=device,
                replacement_device=replacement_device,
                replacement_type=replacement_type,
                description=description,
            )

            old_vehicle = device.vehicle
            old_branch = device.branch
            old_org = device.organization
            old_user = device.owner_user

            _close_active_link(device, operation)
            device.vehicle = None
            device.branch = None
            device.current_holder_organization = None
            device.current_holder_user = None
            if replacement_type == 'permanent_replacement':
                device.organization = None
                device.owner_user = None
            device.management_status = 'faulty'
            device.save()

            replacement_device.management_status = 'installed' if replacement_type == 'temporary_repair' else 'sold'
            replacement_device.vehicle = old_vehicle
            replacement_device.branch = old_branch
            replacement_device.current_holder_organization = old_org
            replacement_device.current_holder_user = old_user
            if replacement_type == 'permanent_replacement':
                replacement_device.organization = old_org
                replacement_device.owner_user = old_user
                replacement_device.current_holder_organization = old_org
                replacement_device.current_holder_user = old_user
            replacement_device.save()

            if subscription:
                _add_to_subscription(
                    replacement_device,
                    subscription,
                    operation,
                    start_date=subscription.start_date,
                    end_date=subscription.end_date,
                )

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
            old_org, old_user, old_vehicle, old_branch = device.organization, device.owner_user, device.vehicle, device.branch
            _close_active_link(device, operation)
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
            raise ValidationError({'device': 'فقط دستگاهی که در وضعیت خرابی/تعمیر است قابل ثبت به عنوان تعمیرشده است.'})
        if not repair_return_action:
            raise ValidationError({'repair_return_action': 'سرنوشت دستگاه پس از تعمیر را مشخص کنید'})

        temp_relation = DeviceReplacementRelation.objects.filter(
            source_device=device, replacement_type='temporary_repair',
        ).select_related('replacement_device').order_by('-replacement_date', '-id').first()
        loaner = temp_relation.replacement_device if temp_relation else None
        loaner_link = (
            loaner.subscription_links.filter(unassigned_at__isnull=True).select_related('subscription').first()
            if loaner else None
        )
        return_subscription = loaner_link.subscription if loaner_link else None

        repair_event = DeviceLifecycleEvent.objects.filter(
            device=device, event_type='sent_to_repair',
        ).select_related('organization', 'user', 'vehicle', 'branch').order_by('-event_date', '-id').first()
        previous_org = repair_event.organization if repair_event else device.organization
        previous_user = repair_event.user if repair_event else device.owner_user
        previous_vehicle = repair_event.vehicle if repair_event else None
        previous_branch = repair_event.branch if repair_event else None
        return_vehicle = loaner.vehicle if loaner else previous_vehicle
        return_branch = loaner.branch if loaner else previous_branch

        if loaner_link:
            loaner_link.unassigned_at = timezone.now()
            loaner_link.removed_by_operation = operation
            loaner_link.save(update_fields=['unassigned_at', 'removed_by_operation'])

        device.vehicle = None
        device.branch = None
        device.current_holder_organization = previous_org
        device.current_holder_user = previous_user

        if repair_return_action == 'return_customer_same_vehicle':
            device.organization, device.owner_user = previous_org, previous_user
            device.vehicle, device.branch = return_vehicle, return_branch
            device.current_holder_organization, device.current_holder_user = previous_org, previous_user
            device.management_status = 'installed'
        elif repair_return_action == 'return_customer_no_vehicle':
            device.organization, device.owner_user = previous_org, previous_user
            device.current_holder_organization, device.current_holder_user = previous_org, previous_user
            device.management_status = 'sold'
        elif repair_return_action == 'sana_warehouse':
            device.organization = device.owner_user = None
            device.current_holder_organization = device.current_holder_user = None
            device.management_status = 'warehouse'
        elif repair_return_action == 'customer_spare':
            device.organization, device.owner_user = previous_org, previous_user
            device.current_holder_organization, device.current_holder_user = previous_org, previous_user
            device.management_status = 'sold'
        elif repair_return_action == 'install_other_vehicle':
            if not target_vehicle:
                raise ValidationError({'target_vehicle': 'برای نصب روی خودروی دیگر، خودروی مقصد را مشخص کنید'})
            if device.organization_id and target_vehicle.organization_id != device.organization_id:
                raise ValidationError({'target_vehicle': 'خودروی مقصد باید متعلق به همان مشتری دستگاه باشد'})
            device.organization, device.owner_user = previous_org, previous_user
            device.current_holder_organization, device.current_holder_user = previous_org, previous_user
            device.vehicle, device.branch = target_vehicle, target_vehicle.branch
            device.management_status = 'installed'
        elif repair_return_action == 'transfer_customer':
            if not target_organization and not target_user:
                raise ValidationError({'target_organization': 'مالک مقصد را مشخص کنید'})
            device.organization, device.owner_user = target_organization, target_user
            device.current_holder_organization, device.current_holder_user = target_organization, target_user
            device.vehicle = target_vehicle
            device.branch = target_vehicle.branch if target_vehicle else None
            device.management_status = 'sold'
        elif repair_return_action == 'retire':
            device.organization, device.owner_user = previous_org, previous_user
            device.current_holder_organization, device.current_holder_user = previous_org, previous_user
            device.management_status = 'retired'
        elif repair_return_action == 'dispose':
            device.organization = device.owner_user = None
            device.current_holder_organization = device.current_holder_user = None
            device.management_status = 'disposed'
        elif repair_return_action == 'other':
            device.management_status = 'warehouse'

        device.save()

        if repair_return_action in {'return_customer_same_vehicle', 'return_customer_no_vehicle', 'customer_spare', 'install_other_vehicle'} and return_subscription:
            _add_to_subscription(device, return_subscription, operation, start_date=return_subscription.start_date, end_date=return_subscription.end_date)
        elif repair_return_action == 'transfer_customer' and target_subscription:
            _add_to_subscription(device, target_subscription, operation)

        if loaner:
            loaner.management_status = 'warehouse'
            loaner.vehicle = loaner.branch = None
            loaner.current_holder_organization = loaner.current_holder_user = None
            loaner.save()

        disposition_labels = {
            'return_customer_same_vehicle': 'به مشتری بازگشت و روی خودرو نصب شد',
            'return_customer_no_vehicle': 'به مشتری بازگشت و فعلاً نصب نشد',
            'sana_warehouse': 'به انبار سانا بازگشت',
            'customer_spare': 'به عنوان دستگاه یدکی به مشتری تحویل شد',
            'install_other_vehicle': 'روی خودروی دیگر نصب شد',
            'transfer_customer': 'به مشتری دیگر منتقل شد',
            'retire': 'بازنشسته شد', 'dispose': 'امحاء شد', 'other': 'طبق توضیحات تکمیلی تعیین شد',
        }
        record_device_lifecycle_event(
            device_operation=operation, device=device, event_type='repaired', performed_by=performed_by,
            subscription=return_subscription or target_subscription, organization=device.organization, user=device.owner_user,
            vehicle=device.vehicle, branch=device.branch, reason=reason or 'repair',
            description=description or f'تعمیر دستگاه پایان یافت؛ {disposition_labels.get(repair_return_action, repair_return_action)}.',
        )
        if loaner:
            record_device_lifecycle_event(
                device_operation=operation, device=loaner, event_type='removed_from_contract', performed_by=performed_by,
                subscription=return_subscription, reason='replacement',
                description=f'دستگاه امانی {loaner.imei} پس از تعیین تکلیف دستگاه {device.imei} به انبار سانا بازگردانده شد.',
            )

    elif operation_type in {'lost', 'stolen'}:
        device.management_status = operation_type
        device.save(update_fields=['management_status', 'updated_at'])
        record_device_lifecycle_event(
                device_operation=operation,
                device=device,
            event_type=operation_type,
            performed_by=performed_by,
            subscription=subscription,
            organization=device.organization,
            user=device.owner_user,
            vehicle=device.vehicle,
            branch=device.branch,
            reason=reason,
            description=description,
        )
        if replacement_device:
            if replacement_device.active_subscription_link or not replacement_device.is_in_warehouse:
                raise ValidationError({'replacement_device': 'دستگاه جایگزین باید در انبار آزاد سانا باشد.'})
            _close_active_link(device, operation)
            replacement_device.organization = device.organization
            replacement_device.owner_user = device.owner_user
            replacement_device.branch = device.branch
            replacement_device.vehicle = device.vehicle
            replacement_device.management_status = 'sold'
            replacement_device.save()
            if subscription:
                _add_to_subscription(replacement_device, subscription, operation)
            DeviceReplacementRelation.objects.create(
                source_device=device,
                replacement_device=replacement_device,
                replacement_type='permanent_replacement',
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
                description=f'جایگزین دستگاه {device.imei} شد.',
            )

    elif operation_type == 'transfer_customer':
        if not target_organization and not target_user:
            raise ValidationError({'target_organization': 'مالک مقصد را مشخص کنید'})
        _close_active_link(device, operation)
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
        record_device_lifecycle_event(
                device_operation=operation,
                device=device, event_type='transferred', performed_by=performed_by,
            subscription=subscription, organization=device.organization,
            user=device.owner_user, vehicle=device.vehicle, branch=target_branch,
            reason=reason, description=description,
        )

    elif operation_type == 'transfer_vehicle':
        if not target_vehicle:
            raise ValidationError({'target_vehicle': 'خودرو مقصد را مشخص کنید'})
        if target_vehicle.organization_id != device.organization_id and device.organization_id:
            raise ValidationError({'target_vehicle': 'خودرو مقصد باید متعلق به همان مشتری دستگاه باشد'})
        old_vehicle = device.vehicle
        device.vehicle = target_vehicle
        device.branch = target_vehicle.branch
        device.save(update_fields=['vehicle', 'branch', 'updated_at'])
        record_device_lifecycle_event(
                device_operation=operation,
                device=device, event_type='transferred', performed_by=performed_by,
            subscription=subscription, organization=device.organization,
            user=device.owner_user, vehicle=target_vehicle, branch=target_vehicle.branch,
            reason=reason, description=description or f'انتقال از خودرو {old_vehicle.plate if old_vehicle else "بدون خودرو"} انجام شد.',
        )

    elif operation_type == 'retire':
        device.management_status = 'retired'
        device.save(update_fields=['management_status', 'updated_at'])
        record_device_lifecycle_event(
                device_operation=operation,
                device=device, event_type='retired', performed_by=performed_by,
            subscription=subscription, organization=device.organization,
            user=device.owner_user, vehicle=device.vehicle, branch=device.branch,
            reason=reason, description=description,
        )

    elif operation_type == 'dispose':
        if device.management_status != 'retired':
            raise ValidationError({'device': 'برای امحاء ابتدا دستگاه باید بازنشسته شود.'})
        device.management_status = 'disposed'
        device.save(update_fields=['management_status', 'updated_at'])
        record_device_lifecycle_event(
                device_operation=operation,
                device=device, event_type='disposed', performed_by=performed_by,
            subscription=subscription, organization=device.organization,
            user=device.owner_user, reason=reason, description=description,
        )
    else:
        raise ValidationError({'operation_type': 'نوع عملیات پشتیبانی نمی‌شود'})

    operation.new_status = device.management_status
    operation.save(update_fields=['new_status'])
    return operation
