from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Device, DeviceOperation, DeviceReplacementRelation, DeviceLifecycleEvent, DeviceOwnershipHistory, DeviceCustomerAccessPeriod
from .lifecycle import record_device_lifecycle_event
from organizations.models import SubscriptionDevice


_CUSTOMER_UNSET = object()


def _customer_kwargs(device=None, organization=_CUSTOMER_UNSET, user=_CUSTOMER_UNSET):
    if organization is _CUSTOMER_UNSET:
        organization = device.organization if device else None
    if user is _CUSTOMER_UNSET:
        user = device.owner_user if device else None
    if organization:
        return {'organization': organization, 'user': None}
    if user:
        return {'organization': None, 'user': user}
    return {'organization': None, 'user': None}


def _current_customer(device, subscription=None):
    """Resolve the contract customer/current holder without confusing legal ownership."""
    if subscription is not None:
        if subscription.customer_type == 'organization':
            return {'organization': subscription.organization, 'user': None}
        if subscription.customer_type == 'personal':
            return {'organization': None, 'user': subscription.user}
    if device.current_holder_organization_id is not None or device.current_holder_user_id is not None:
        return {
            'organization': device.current_holder_organization,
            'user': device.current_holder_user,
        }
    return {'organization': device.organization, 'user': device.owner_user}


def _validate_transfer_target(*, organization, user, branch=None, vehicle=None, subscription=None):
    if bool(organization) == bool(user):
        raise ValidationError({
            'target_organization': 'باید دقیقاً یک مشتری سازمانی یا شخصی برای انتقال انتخاب شود.'
        })

    if organization:
        if organization.status != 'active':
            raise ValidationError({'target_organization': 'سازمان مقصد باید فعال باشد.'})
        if branch and (
            branch.organization_id != organization.id
            or branch.status != 'active'
        ):
            raise ValidationError({'target_branch': 'شعبه مقصد باید فعال و متعلق به سازمان مشتری مقصد باشد.'})
        if vehicle and (
            vehicle.organization_id != organization.id
            or vehicle.owner_user_id is not None
            or (vehicle.branch_id and vehicle.branch.status != 'active')
            or (branch and vehicle.branch_id != branch.id)
        ):
            raise ValidationError({'target_vehicle': 'خودروی مقصد متعلق به سازمان یا شعبه انتخاب‌شده نیست.'})
        if subscription and (
            subscription.customer_type != 'organization'
            or subscription.organization_id != organization.id
            or subscription.user_id is not None
            or subscription.computed_status != 'active'
        ):
            raise ValidationError({'target_subscription': 'قرارداد مقصد باید فعال و متعلق به سازمان انتخاب‌شده باشد.'})
    else:
        if not user.is_active or not user.is_personal_user:
            raise ValidationError({
                'target_user': 'انتقال شخصی فقط به حساب دارای نقش مشتری شخصی فعال مجاز است.'
            })
        if branch:
            raise ValidationError({'target_branch': 'مشتری شخصی نمی‌تواند شعبه سازمانی داشته باشد.'})
        if vehicle and (
            vehicle.owner_user_id != user.id
            or vehicle.organization_id is not None
            or vehicle.branch_id is not None
        ):
            raise ValidationError({'target_vehicle': 'خودروی مقصد متعلق به کاربر شخصی انتخاب‌شده نیست.'})
        if subscription and (
            subscription.customer_type != 'personal'
            or subscription.user_id != user.id
            or subscription.organization_id is not None
            or subscription.computed_status != 'active'
        ):
            raise ValidationError({'target_subscription': 'قرارداد مقصد باید فعال و متعلق به کاربر شخصی انتخاب‌شده باشد.'})


def _validate_device_customer_assignment(device, subscription):
    """Validate a warehouse device against the exact contract customer and its current holder."""
    if device.management_status in {'faulty', 'in_repair', 'ready', 'lost', 'stolen', 'unusable', 'disposed'}:
        raise ValidationError({
            'device': 'دستگاه در وضعیت فعلی قابل اتصال به قرارداد نیست؛ ابتدا وضعیت عملیاتی آن را تعیین تکلیف کنید.'
        })

    if subscription.computed_status != 'active':
        raise ValidationError({'subscription': 'اتصال دستگاه به قرارداد غیرفعال یا منقضی مجاز نیست.'})

    if subscription.customer_type == 'organization':
        if (
            not subscription.organization_id
            or subscription.user_id is not None
            or subscription.organization.status != 'active'
        ):
            raise ValidationError({
                'subscription': 'قرارداد سازمانی باید به سازمان فعال و معتبر تعلق داشته باشد.'
            })
        target_organization_id = subscription.organization_id
        target_user_id = None
    elif subscription.customer_type == 'personal':
        if (
            not subscription.user_id
            or not subscription.user.is_active
            or not subscription.user.is_personal_user
            or subscription.organization_id is not None
        ):
            raise ValidationError({
                'subscription': 'مشتری قرارداد شخصی باید حساب فعال با نقش مشتری شخصی باشد.'
            })
        target_organization_id = None
        target_user_id = subscription.user_id
    else:
        raise ValidationError({'subscription': 'نوع مشتری قرارداد نامعتبر است.'})

    if target_organization_id is not None:
        if device.branch_id and (
            device.branch.organization_id != target_organization_id
            or device.branch.status != 'active'
        ):
            raise ValidationError({
                'device': 'شعبه فعلی دستگاه باید فعال و متعلق به سازمان قرارداد باشد.'
            })
        if device.vehicle_id and (
            device.vehicle.organization_id != target_organization_id
            or device.vehicle.owner_user_id is not None
            or device.vehicle.branch_id != device.branch_id
        ):
            raise ValidationError({
                'device': 'خودروی متصل به دستگاه باید متعلق به سازمان قرارداد و در همان شعبه باشد.'
            })
    else:
        if device.branch_id:
            raise ValidationError({
                'device': 'دستگاه مشتری شخصی نمی‌تواند به شعبه سازمانی متصل باشد.'
            })
        if device.vehicle_id and (
            device.vehicle.owner_user_id != target_user_id
            or device.vehicle.organization_id is not None
            or device.vehicle.branch_id is not None
        ):
            raise ValidationError({
                'device': 'خودروی متصل به دستگاه باید متعلق به همان مشتری شخصی باشد.'
            })

    current_organization_id = device.current_holder_organization_id
    current_user_id = device.current_holder_user_id
    if (
        (current_organization_id is not None or current_user_id is not None)
        and (
            current_organization_id != target_organization_id
            or current_user_id != target_user_id
        )
    ):
        raise ValidationError({
            'device': 'دستگاه در حال حاضر به مشتری دیگری تحویل شده است؛ ابتدا انتقال رسمی مشتری را انجام دهید.'
        })


def _close_customer_access(device, when=None):
    when = when or timezone.now()
    latest_open_start = DeviceCustomerAccessPeriod.objects.filter(
        device=device,
        ended_at__isnull=True,
    ).order_by('-started_at', '-id').values_list('started_at', flat=True).first()
    if latest_open_start and when < latest_open_start:
        # Clock adjustments or legacy future-dated rows must never create
        # a negative access interval.
        when = latest_open_start
    DeviceCustomerAccessPeriod.objects.filter(device=device, ended_at__isnull=True).update(ended_at=when)


def _open_customer_access(device, subscription=None, branch=None, organization=_CUSTOMER_UNSET, user=_CUSTOMER_UNSET, started_at=None, reason=''):
    # A contract is the authority for customer identity. Legal ownership must
    # never be substituted for the customer who receives the service.
    if subscription is not None:
        if organization is _CUSTOMER_UNSET:
            organization = subscription.organization
        if user is _CUSTOMER_UNSET:
            user = subscription.user
    else:
        if organization is _CUSTOMER_UNSET:
            organization = device.current_holder_organization or device.organization
        if user is _CUSTOMER_UNSET:
            user = device.current_holder_user or device.owner_user
    customer = _customer_kwargs(device, organization, user)
    if not customer['organization'] and not customer['user']:
        _close_customer_access(device, started_at or timezone.now())
        return None

    close_time = started_at or timezone.now()
    if subscription is None:
        # A customer relationship without a contract must never open an access
        # period. Close any previous period so stale rows cannot linger.
        _close_customer_access(device, close_time)
        return None

    current_link = subscription.subscription_devices.filter(
        device=device,
        unassigned_at__isnull=True,
    ).order_by('-assigned_at', '-id').first()
    if current_link is None or not current_link.is_active:
        _close_customer_access(device, close_time)
        return None
    if subscription.computed_status != 'active':
        _close_customer_access(device, close_time)
        return None
    close_time = max(close_time, current_link.assigned_at)

    if customer['organization']:
        if (
            subscription.customer_type != 'organization'
            or subscription.organization_id != customer['organization'].pk
        ):
            raise ValidationError({
                'target_subscription': 'قرارداد باید متعلق به همان سازمان مقصد باشد.'
            })
        if branch and branch.organization_id != customer['organization'].pk:
            raise ValidationError({
                'target_branch': 'شعبه انتخاب‌شده متعلق به سازمان قرارداد نیست.'
            })
    elif customer['user']:
        if (
            subscription.customer_type != 'personal'
            or subscription.user_id != customer['user'].pk
        ):
            raise ValidationError({
                'target_subscription': 'قرارداد باید متعلق به همان مشتری شخصی باشد.'
            })

    open_periods = list(
        DeviceCustomerAccessPeriod.objects.filter(
            device=device, ended_at__isnull=True
        ).order_by('-started_at', '-id')
    )
    current = open_periods[0] if open_periods else None
    if current:
        same_customer = (
            current.organization_id == getattr(customer['organization'], 'id', None)
            and current.user_id == getattr(customer['user'], 'id', None)
        )
        same_subscription = current.subscription_id == subscription.pk
        same_branch = current.branch_id == getattr(branch, 'pk', None)
        same_assignment = current_link.assigned_at <= current.started_at

        # A new contract, assignment, or branch starts a new access period,
        # even when the legal customer remains unchanged. Never rewrite history.
        if same_customer and same_subscription and same_branch and same_assignment:
            # Collapse duplicate open rows from legacy data while retaining
            # the newest valid period for the same customer/contract/branch.
            stale_period_ids = [period.pk for period in open_periods[1:]]
            if stale_period_ids:
                for stale_period in open_periods[1:]:
                    DeviceCustomerAccessPeriod.objects.filter(
                        pk=stale_period.pk,
                        ended_at__isnull=True,
                    ).update(ended_at=max(close_time, stale_period.started_at))
            return current

        close_time = max(close_time, current.started_at)
        _close_customer_access(device, close_time)

    return DeviceCustomerAccessPeriod.objects.create(
        device=device,
        subscription=subscription,
        branch=branch,
        started_at=close_time,
        reason=reason,
        **customer,
    )


def _close_ownership(device, when=None):
    when = when or timezone.now()
    latest_open_start = DeviceOwnershipHistory.objects.filter(
        device=device,
        ended_at__isnull=True,
    ).order_by('-started_at', '-id').values_list('started_at', flat=True).first()
    if latest_open_start and when < latest_open_start:
        when = latest_open_start
    DeviceOwnershipHistory.objects.filter(device=device, ended_at__isnull=True).update(ended_at=when)


def _open_ownership(device, organization=_CUSTOMER_UNSET, user=_CUSTOMER_UNSET, started_at=None, reason=''):
    # Ownership history records legal ownership only, never the contract customer.
    if organization is _CUSTOMER_UNSET and user is _CUSTOMER_UNSET:
        organization = device.organization
        user = device.owner_user
    customer = _customer_kwargs(device, organization, user)
    if not customer['organization'] and not customer['user']:
        return None
    current = DeviceOwnershipHistory.objects.filter(device=device, ended_at__isnull=True).order_by('-started_at', '-id').first()
    same_customer = current and current.organization_id == getattr(customer['organization'], 'id', None) and current.owner_user_id == getattr(customer['user'], 'id', None)
    if same_customer:
        return current
    ownership_started_at = started_at or timezone.now()
    if current:
        ownership_started_at = max(ownership_started_at, current.started_at)
        _close_ownership(device, ownership_started_at)
    ownership_customer = {
        'organization': customer['organization'],
        'owner_user': customer['user'],
    }
    return DeviceOwnershipHistory.objects.create(
        device=device,
        started_at=ownership_started_at,
        reason=reason,
        **ownership_customer,
    )


def _close_active_link(device, operation):
    links = device.subscription_links.filter(
        unassigned_at__isnull=True
    ).select_related('subscription').order_by('-assigned_at', '-id')
    link = links.first()
    if link:
        # Legacy data may contain more than one open contract link for the
        # same device. A customer transfer/removal must close every one of
        # them, otherwise an old customer could retain device access.
        SubscriptionDevice.objects.filter(
            device=device,
            unassigned_at__isnull=True,
        ).update(unassigned_at=timezone.now())
    return link


def _add_to_subscription(device, subscription, operation, start_date=None, end_date=None):
    if not subscription:
        raise ValidationError({'target_subscription': 'انتخاب قرارداد مقصد الزامی است'})
    if subscription.computed_status != 'active':
        raise ValidationError({'target_subscription': 'افزودن دستگاه به قرارداد غیرفعال یا منقضی مجاز نیست.'})
    start_date = start_date or subscription.start_date
    end_date = end_date or subscription.end_date
    if start_date > end_date:
        raise ValidationError({'target_subscription': 'بازه قرارداد مقصد نامعتبر است'})
    try:
        return SubscriptionDevice.objects.create(
            subscription=subscription,
            device=device,
            start_date=start_date,
            end_date=end_date,
        )
    except DjangoValidationError as exc:
        raise ValidationError({'device': exc.messages}) from exc


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
            if replacement_device.active_subscription_link:
                raise ValidationError({'replacement_device': 'دستگاه جایگزین در قرارداد دیگری فعال است.'})
            if replacement_device.management_status != 'warehouse' or not replacement_device.is_in_warehouse:
                raise ValidationError({'replacement_device': 'دستگاه جایگزین باید در انبار آزاد سانا باشد.'})

            old_vehicle = device.vehicle
            old_branch = device.branch
            customer = _current_customer(device, subscription)
            old_org = customer['organization']
            old_user = customer['user']

            DeviceReplacementRelation.objects.create(
                source_device=device,
                replacement_device=replacement_device,
                replacement_type=replacement_type,
                description=description,
            )

            # تعمیر، مالکیت قانونی و سابقه قرارداد را حفظ می‌کند؛ دسترسی جاری بسته می‌شود.
            _close_customer_access(device)
            device.vehicle = None
            device.branch = None
            device.current_holder_organization = None
            device.current_holder_user = None
            device.management_status = 'in_repair'
            device.save()

            replacement_device.management_status = (
                'installed'
            )
            replacement_device.vehicle = old_vehicle
            replacement_device.branch = old_branch
            replacement_device.current_holder_organization = old_org
            replacement_device.current_holder_user = old_user
            if replacement_type == 'permanent_replacement':
                replacement_device.organization = device.organization
                replacement_device.owner_user = device.owner_user
            replacement_device.save()

            if replacement_type == 'permanent_replacement':
                _close_active_link(device, operation)
                _open_ownership(
                    replacement_device,
                    organization=replacement_device.organization,
                    user=replacement_device.owner_user,
                    reason='permanent_replacement',
                )
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
                organization=old_org,
                user=old_user,
                vehicle=replacement_device.vehicle,
                branch=replacement_device.branch,
                reason='replacement',
                description=f'به عنوان جایگزین دستگاه {device.imei} به قرارداد متصل شد.',
            )
        else:
            customer = _current_customer(device, subscription)
            old_org = customer['organization']
            old_user = customer['user']
            old_vehicle = device.vehicle
            old_branch = device.branch

            _close_customer_access(device)
            device.vehicle = None
            device.branch = None
            device.current_holder_organization = None
            device.current_holder_user = None
            device.management_status = 'in_repair'
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

    elif operation_type in {'temporary_replacement', 'permanent_replacement'}:
        if device.management_status not in {'faulty', 'in_repair', 'lost', 'stolen'}:
            raise ValidationError({
                'device': 'فقط دستگاه خراب، گمشده یا سرقت‌شده می‌تواند بعداً جایگزین دریافت کند.'
            })
        if not replacement_device:
            raise ValidationError({'replacement_device': 'دستگاه جایگزین را انتخاب کنید.'})
        if replacement_type not in {'temporary_repair', 'permanent_replacement'}:
            raise ValidationError({'replacement_type': 'نوع جایگزینی را مشخص کنید.'})
        expected_type = 'temporary_repair' if operation_type == 'temporary_replacement' else 'permanent_replacement'
        if replacement_type != expected_type:
            raise ValidationError({'replacement_type': 'نوع جایگزینی با عملیات انتخاب‌شده هماهنگ نیست.'})
        if replacement_device.active_subscription_link or not replacement_device.is_in_warehouse:
            raise ValidationError({'replacement_device': 'دستگاه جایگزین باید در انبار آزاد سانا باشد.'})

        previous_event = DeviceLifecycleEvent.objects.filter(
            device=device,
            event_type__in=['sent_to_repair', 'lost', 'stolen'],
        ).order_by('-event_date', '-id').first()
        previous_vehicle = previous_event.vehicle if previous_event else None
        previous_branch = previous_event.branch if previous_event else None
        customer = _current_customer(device, subscription)
        _close_customer_access(device)
        customer_org = customer['organization']
        customer_user = customer['user']

        DeviceReplacementRelation.objects.create(
            source_device=device,
            replacement_device=replacement_device,
            replacement_type=replacement_type,
            description=description or 'جایگزینی دستگاه در ادامه عملیات قبلی.',
        )

        replacement_device.management_status = (
            'installed'
        )
        replacement_device.vehicle = previous_vehicle
        replacement_device.branch = previous_branch
        replacement_device.current_holder_organization = customer_org
        replacement_device.current_holder_user = customer_user
        if replacement_type == 'permanent_replacement':
            replacement_device.organization = device.organization
            replacement_device.owner_user = device.owner_user
        replacement_device.save()

        if replacement_type == 'permanent_replacement':
            _open_ownership(
                replacement_device,
                organization=replacement_device.organization,
                user=replacement_device.owner_user,
                reason='permanent_replacement',
            )

        if subscription:
            _add_to_subscription(replacement_device, subscription, operation)
            _open_customer_access(
                replacement_device,
                subscription=subscription,
                branch=previous_branch,
                organization=customer_org,
                user=customer_user,
                reason='replacement',
            )

        record_device_lifecycle_event(
            device_operation=operation,
            device=replacement_device,
            event_type='assigned_to_contract',
            performed_by=performed_by,
            subscription=subscription,
            organization=customer_org,
            user=customer_user,
            vehicle=previous_vehicle,
            branch=previous_branch,
            reason='replacement',
            description=f'به عنوان جایگزین دستگاه {device.imei} به قرارداد متصل شد.',
        )

    elif operation_type == 'repaired':
        if device.management_status not in {'faulty', 'in_repair'}:
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

        _close_customer_access(device)
        customer = _current_customer(device, subscription)
        record_device_lifecycle_event(
            device_operation=operation,
            device=device,
            event_type='repaired',
            performed_by=performed_by,
            subscription=subscription,
            organization=customer['organization'],
            user=customer['user'],
            vehicle=None,
            branch=None,
            reason=reason or 'repair',
            description=description or 'تعمیر دستگاه پایان یافت و دستگاه آماده تعیین تکلیف شد.',
        )

    elif operation_type in {'lost', 'stolen'}:
        if replacement_device:
            if replacement_type not in {'temporary_repair', 'permanent_replacement'}:
                raise ValidationError({'replacement_type': 'نوع جایگزینی را مشخص کنید'})
            if replacement_device.active_subscription_link or not replacement_device.is_in_warehouse:
                raise ValidationError({'replacement_device': 'دستگاه جایگزین باید در انبار آزاد سانا باشد.'})

        old_vehicle = device.vehicle
        old_branch = device.branch
        customer = _current_customer(device, subscription)
        _close_customer_access(device)
        old_org = customer['organization']
        old_user = customer['user']

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
                'installed'
            )
            if replacement_type == 'permanent_replacement':
                _close_active_link(device, operation)
                replacement_device.organization = device.organization
                replacement_device.owner_user = device.owner_user
            replacement_device.save()

            if replacement_type == 'permanent_replacement' and (
                replacement_device.organization_id or replacement_device.owner_user_id
            ):
                _open_ownership(
                    replacement_device,
                    organization=replacement_device.organization,
                    user=replacement_device.owner_user,
                    reason='permanent_replacement',
                )

            if subscription:
                _add_to_subscription(replacement_device, subscription, operation)
                _open_customer_access(
                    replacement_device,
                    subscription=subscription,
                    branch=old_branch,
                    organization=old_org,
                    user=old_user,
                    reason='replacement',
                )

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
                organization=old_org,
                user=old_user,
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
        customer = _current_customer(device, subscription)
        device.management_status = 'ready'
        device.vehicle = None
        device.branch = None
        device.current_holder_organization = None
        device.current_holder_user = None
        device.save()

        record_device_lifecycle_event(
            device_operation=operation,
            device=device,
            event_type='found',
            performed_by=performed_by,
            subscription=subscription,
            organization=customer['organization'],
            user=customer['user'],
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
        previous_customer = _current_customer(device, subscription)
        has_current_customer = (
            subscription is not None
            or device.current_holder_organization_id is not None
            or device.current_holder_user_id is not None
        )
        if has_current_customer:
            previous_org = previous_customer['organization']
            previous_user = previous_customer['user']
        else:
            previous_org = (
                previous_event.organization
                if previous_event and previous_event.organization_id
                else previous_customer['organization']
            )
            previous_user = (
                previous_event.user
                if previous_event and previous_event.user_id
                else previous_customer['user']
            )

        if outcome_action == 'return_customer_same_vehicle':
            target = previous_vehicle
            if not target:
                raise ValidationError({
                    'outcome_action': 'خودروی قبلی برای بازگشت مشخص نیست؛ خودروی مقصد را انتخاب کنید.'
                })
            if Device.objects.filter(vehicle=target).exclude(pk=device.pk).exclude(
                management_status__in=['faulty', 'in_repair', 'lost', 'stolen', 'unusable', 'disposed']
            ).exists():
                raise ValidationError({
                    'outcome_action': 'خودروی قبلی هنوز دستگاه دیگری دارد؛ ابتدا تکلیف آن دستگاه را مشخص کنید.'
                })
            device.vehicle = target
            device.branch = target.branch
            device.current_holder_organization = previous_org
            device.current_holder_user = previous_user
            device.management_status = 'installed'

        elif outcome_action == 'return_customer_no_vehicle':
            device.vehicle = None
            device.branch = None
            device.current_holder_organization = previous_org
            device.current_holder_user = previous_user
            device.management_status = 'installed'

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
            device.management_status = 'installed'

        elif outcome_action == 'install_other_vehicle':
            if not target_vehicle:
                raise ValidationError({
                    'target_vehicle': 'برای نصب روی خودروی دیگر، خودروی مقصد را مشخص کنید'
                })
            if previous_org:
                if (
                    target_vehicle.organization_id != previous_org.id
                    or target_vehicle.owner_user_id is not None
                    or (target_vehicle.branch_id and target_vehicle.branch.organization_id != previous_org.id)
                ):
                    raise ValidationError({
                        'target_vehicle': 'خودروی مقصد باید متعلق به همان سازمان مشتری باشد'
                    })
            elif previous_user:
                if (
                    target_vehicle.owner_user_id != previous_user.id
                    or target_vehicle.organization_id is not None
                    or target_vehicle.branch_id is not None
                ):
                    raise ValidationError({
                        'target_vehicle': 'خودروی مقصد باید متعلق به همان کاربر شخصی باشد'
                    })
            else:
                raise ValidationError({'device': 'مشتری قبلی دستگاه مشخص نیست.'})
            if Device.objects.filter(vehicle=target_vehicle).exclude(pk=device.pk).exclude(
                management_status__in=['faulty', 'in_repair', 'lost', 'stolen', 'unusable', 'disposed']
            ).exists():
                raise ValidationError({'target_vehicle': 'خودروی مقصد در حال حاضر دستگاه دیگری دارد.'})
            device.vehicle = target_vehicle
            device.branch = target_vehicle.branch
            device.current_holder_organization = previous_org
            device.current_holder_user = previous_user
            device.management_status = 'installed'

        elif outcome_action == 'transfer_customer':
            _validate_transfer_target(
                organization=target_organization,
                user=target_user,
                branch=target_branch,
                vehicle=target_vehicle,
                subscription=target_subscription,
            )
            _close_active_link(device, operation)
            _close_customer_access(device)
            _close_ownership(device)
            device.organization = target_organization
            device.owner_user = target_user
            device.current_holder_organization = target_organization
            device.current_holder_user = target_user
            device.vehicle = target_vehicle
            device.branch = target_vehicle.branch if target_vehicle else target_branch
            device.management_status = 'installed'

        elif outcome_action == 'retire':
            device.vehicle = None
            device.branch = None
            device.current_holder_organization = previous_org
            device.current_holder_user = previous_user
            device.management_status = 'unusable'

        elif outcome_action == 'dispose':
            _close_active_link(device, operation)
            _close_customer_access(device)
            _close_ownership(device)
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
            device.current_holder_organization = None
            device.current_holder_user = None
            device.management_status = 'ready'

        else:
            raise ValidationError({'outcome_action': 'تکلیف انتخاب‌شده پشتیبانی نمی‌شود.'})

        device.save()

        if outcome_action == 'transfer_customer':
            if device.organization_id or device.owner_user_id:
                _open_ownership(
                    device,
                    organization=device.organization,
                    user=device.owner_user,
                    reason='customer_transfer',
                )
            if target_subscription:
                _add_to_subscription(device, target_subscription, operation)
                _open_customer_access(
                    device,
                    subscription=target_subscription,
                    branch=device.branch,
                    organization=target_organization,
                    user=target_user,
                    reason='customer_transfer',
                )
        elif outcome_action in {'sana_warehouse', 'retire', 'other'}:
            _close_active_link(device, operation)
            _close_customer_access(device)
        elif outcome_action in {
            'return_customer_same_vehicle', 'return_customer_no_vehicle',
            'customer_spare', 'install_other_vehicle',
        }:
            current_link = device.active_subscription_link
            if (
                current_link
                and current_link.is_active
                and current_link.subscription.computed_status == 'active'
            ):
                _open_customer_access(
                    device,
                    subscription=current_link.subscription,
                    branch=device.branch,
                    organization=previous_org,
                    user=previous_user,
                    reason='disposition_return',
                )
            else:
                _close_customer_access(device)

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
        event_customer = (
            {'organization': target_organization, 'user': target_user}
            if outcome_action == 'transfer_customer'
            else {'organization': previous_org, 'user': previous_user}
        )
        record_device_lifecycle_event(
            device_operation=operation,
            device=device,
            event_type='disposition',
            performed_by=performed_by,
            subscription=target_subscription or subscription,
            organization=event_customer['organization'],
            user=event_customer['user'],
            vehicle=device.vehicle,
            branch=device.branch,
            reason=reason or 'other',
            description=description or disposition_labels[outcome_action],
        )

    elif operation_type == 'transfer_customer':
        _validate_transfer_target(
            organization=target_organization,
            user=target_user,
            branch=target_branch,
            vehicle=target_vehicle,
            subscription=target_subscription,
        )
        _close_active_link(device, operation)
        _close_customer_access(device)
        _close_ownership(device)
        device.organization = target_organization
        device.owner_user = target_user
        device.current_holder_organization = target_organization
        device.current_holder_user = target_user
        device.branch = None
        device.vehicle = None
        device.management_status = 'installed'
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
        customer = _current_customer(device, subscription)
        if customer['organization'] is None or target_branch.organization_id != customer['organization'].pk:
            raise ValidationError({'target_branch': 'شعبه مقصد باید متعلق به سازمان مشتری فعلی باشد.'})
        if target_branch.status != 'active':
            raise ValidationError({'target_branch': 'شعبه مقصد باید فعال باشد.'})
        device.branch = target_branch
        device.save(update_fields=['branch', 'updated_at'])
        _open_customer_access(device, subscription=subscription, branch=target_branch)
        record_device_lifecycle_event(
            device_operation=operation,
            device=device,
            event_type='transferred',
            performed_by=performed_by,
            subscription=subscription,
            organization=customer['organization'],
            user=customer['user'],
            vehicle=device.vehicle,
            branch=target_branch,
            reason=reason,
            description=description,
        )

    elif operation_type == 'transfer_vehicle':
        if not target_vehicle:
            raise ValidationError({'target_vehicle': 'خودرو مقصد را مشخص کنید'})
        customer = _current_customer(device, subscription)
        if customer['organization']:
            if (
                target_vehicle.organization_id != customer['organization'].pk
                or target_vehicle.owner_user_id is not None
            ):
                raise ValidationError({'target_vehicle': 'خودرو مقصد باید متعلق به همان سازمان مشتری باشد.'})
        elif customer['user']:
            if (
                target_vehicle.owner_user_id != customer['user'].pk
                or target_vehicle.organization_id is not None
                or target_vehicle.branch_id is not None
            ):
                raise ValidationError({'target_vehicle': 'خودرو مقصد باید متعلق به همان مشتری شخصی باشد.'})
        else:
            raise ValidationError({'device': 'مشتری فعلی دستگاه مشخص نیست.'})
        if Device.objects.filter(vehicle=target_vehicle).exclude(pk=device.pk).exclude(
            management_status__in=['faulty', 'in_repair', 'lost', 'stolen', 'unusable', 'disposed']
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
            organization=customer['organization'],
            user=customer['user'],
            vehicle=target_vehicle,
            branch=target_vehicle.branch,
            reason=reason,
            description=description or (
                f'انتقال از خودرو {old_vehicle.plate if old_vehicle else "بدون خودرو"} انجام شد.'
            ),
        )

    elif operation_type == 'retire':
        customer = _current_customer(device, subscription)
        _close_active_link(device, operation)
        _close_customer_access(device)
        device.management_status = 'unusable'
        device.vehicle = None
        device.branch = None
        device.save(update_fields=['management_status', 'vehicle', 'branch', 'updated_at'])
        record_device_lifecycle_event(
            device_operation=operation,
            device=device,
            event_type='retired',
            performed_by=performed_by,
            subscription=subscription,
            organization=customer['organization'],
            user=customer['user'],
            reason=reason,
            description=description,
        )

    elif operation_type == 'dispose':
        if device.management_status != 'unusable':
            raise ValidationError({'device': 'برای امحاء ابتدا دستگاه باید از چرخه استفاده خارج شده باشد.'})
        customer = _current_customer(device, subscription)
        _close_active_link(device, operation)
        _close_customer_access(device)
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
            organization=customer['organization'],
            user=customer['user'],
            reason=reason,
            description=description,
        )
    else:
        raise ValidationError({'operation_type': 'نوع عملیات پشتیبانی نمی‌شود'})

    operation.new_status = device.management_status
    operation.save(update_fields=['new_status'])
    return operation
