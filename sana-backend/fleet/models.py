from django.db import models
from django.conf import settings
from django.utils import timezone


class VehicleType(models.Model):
    """نوع خودرو — توسط خود مشتری تعریف می‌شود"""
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='vehicle_types',
        verbose_name='سازمان'
    )
    name = models.CharField(max_length=100, verbose_name='نام نوع')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'نوع خودرو'
        verbose_name_plural = 'انواع خودرو'
        ordering = ['name']

    def __str__(self):
        return self.name


class Vehicle(models.Model):
    """خودرو"""

    # مالکیت — یکی از این دو پر می‌شود
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='vehicles',
        verbose_name='سازمان'
    )
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='personal_vehicles',
        verbose_name='مالک شخصی'
    )
    branch = models.ForeignKey(
        'organizations.Branch',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='vehicles',
        verbose_name='شعبه'
    )

    # اطلاعات خودرو
    plate = models.CharField(max_length=20, verbose_name='پلاک')
    vehicle_type = models.ForeignKey(
        VehicleType,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='نوع خودرو'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'خودرو'
        verbose_name_plural = 'خودروها'
        ordering = ['plate']

    def __str__(self):
        return self.plate


class DeviceModel(models.Model):
    """کاتالوگ ثابت مدل‌های GPS سازگار با نسخه مشخص Traccar."""

    manufacturer = models.CharField(max_length=100, verbose_name='سازنده')
    name = models.CharField(max_length=100, verbose_name='نام مدل')
    code = models.CharField(max_length=50, verbose_name='کد مدل')
    protocol = models.CharField(max_length=50, verbose_name='پروتکل Traccar')
    # پورت پیش‌فرضی که Traccar برای پروتکل این مدل معرفی کرده است؛
    # ممکن است در تنظیمات نصب واقعی سرور تغییر داده شده باشد.
    port = models.PositiveIntegerField(null=True, blank=True, verbose_name='پورت پیش‌فرض Traccar')
    traccar_version = models.CharField(max_length=20, default='6.16.0', verbose_name='نسخه Traccar')
    source_url = models.URLField(max_length=300, blank=True, default='', verbose_name='منبع')
    is_verified = models.BooleanField(default=False, verbose_name='پشتیبانی نسخه تأیید شده')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'مدل دستگاه'
        verbose_name_plural = 'مدل‌های دستگاه'
        ordering = ['manufacturer', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['manufacturer', 'name', 'traccar_version'],
                name='fleet_dmodel_brand_ver_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.manufacturer} — {self.name}'

class Device(models.Model):
    """دستگاه GPS"""

    MANAGEMENT_STATUS_CHOICES = [
        ('warehouse', 'در انبار'),
        ('installed', 'نصب شده'),
        ('active', 'فعال'),
        ('ready', 'آماده تعیین تکلیف'),
        ('in_repair', 'در حال تعمیر'),
        ('faulty', 'خراب'),
        ('lost', 'گمشده'),
        ('stolen', 'سرقت شده'),
        ('disconnected', 'قطع سرویس'),
        ('unusable', 'غیرقابل استفاده'),
        ('disposed', 'امحاء شده'),
    ]

    imei = models.CharField(max_length=20, unique=True, verbose_name='IMEI')
    # مدل دستگاه اختیاری است؛ ثبت اولیه فقط با IMEI انجام می‌شود.
    device_model = models.ForeignKey(
        DeviceModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='devices',
        verbose_name='مدل دستگاه'
    )
    # Actual protocol is mirrored from Traccar Position.protocol; the selected
    # DeviceModel catalog protocol is only a fallback before the first position.
    protocol = models.CharField(
        max_length=50,
        blank=True,
        default='',
        verbose_name='پروتکل گزارش‌شده توسط Traccar',
        help_text='از فیلد protocol آخرین موقعیت دریافت‌شده از Traccar به‌روزرسانی می‌شود.',
    )

    # مالکیت — یکی از این دو
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='devices',
        verbose_name='سازمان'
    )
    owner_user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='personal_devices',
        verbose_name='مالک شخصی'
    )
    branch = models.ForeignKey(
        'organizations.Branch',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='devices',
        verbose_name='شعبه'
    )

    # محل/تحویل‌گیرنده فعلی (از مالکیت مستقل است؛ برای دستگاه امانی/تعمیراتی)
    current_holder_organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='held_devices',
        verbose_name='تحویل‌گیرنده فعلی'
    )
    current_holder_user = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='held_devices_personal',
        verbose_name='تحویل‌گیرنده شخصی'
    )

    # SIM
    sim_number = models.CharField(max_length=20, blank=True, verbose_name='شماره SIM')

    # نصب روی خودرو
    vehicle = models.ForeignKey(
        'fleet.Vehicle',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='devices',
        verbose_name='خودرو'
    )

    management_status = models.CharField(
        max_length=20, choices=MANAGEMENT_STATUS_CHOICES,
        default='warehouse', verbose_name='وضعیت مدیریتی'
    )

    installed_at = models.DateField(null=True, blank=True, verbose_name='تاریخ نصب')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'دستگاه'
        verbose_name_plural = 'دستگاه‌ها'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=(
                    (models.Q(organization__isnull=True) & models.Q(owner_user__isnull=True))
                    | (models.Q(organization__isnull=False) & models.Q(owner_user__isnull=True))
                    | (models.Q(organization__isnull=True) & models.Q(owner_user__isnull=False))
                ),
                name='device_legal_owner_shape',
            ),
            models.CheckConstraint(
                condition=(
                    (models.Q(current_holder_organization__isnull=True) & models.Q(current_holder_user__isnull=True))
                    | (models.Q(current_holder_organization__isnull=False) & models.Q(current_holder_user__isnull=True))
                    | (models.Q(current_holder_organization__isnull=True) & models.Q(current_holder_user__isnull=False))
                ),
                name='device_holder_shape',
            ),
        ]

    def __str__(self):
        return self.imei

    @property
    def active_subscription_link(self):
        """اتصال فعال این دستگاه به قرارداد"""
        return self.subscription_links.filter(unassigned_at__isnull=True).first()

    @property
    def current_subscription(self):
        """قرارداد فعلی این دستگاه"""
        link = self.active_subscription_link
        return link.subscription if link else None

    @property
    def is_in_warehouse(self):
        """آیا این دستگاه واقعاً در انبار است؟"""
        return (
            self.management_status == 'warehouse'
            and self.active_subscription_link is None
        )

    @property
    def is_data_active(self):
        """آیا داده‌ی این دستگاه باید دریافت بشه؟"""
        link = self.active_subscription_link
        if not link:
            return False
        if self.management_status in {'warehouse', 'faulty', 'in_repair', 'ready', 'lost', 'stolen', 'disconnected', 'unusable', 'disposed'}:
            return False

        # Contract state is authoritative for service availability. A suspended,
        # cancelled, or expired contract must not be reported as data-active even
        # when its historical device link remains open.
        subscription = link.subscription
        today = timezone.localdate()
        now = timezone.now()
        if (
            subscription.computed_status != 'active'
            or subscription.start_date > today
            or subscription.end_date < today
            or not link.is_active
        ):
            return False

        # A live contract link and an open customer-access period must agree.
        # Historical/closed access periods never grant live GPS visibility.
        access = self.customer_access_periods.filter(
            subscription_id=subscription.pk,
            started_at__lte=now,
            ended_at__isnull=True,
        )
        if subscription.customer_type == 'organization':
            if subscription.organization.status != 'active':
                return False
            access = access.filter(
                organization_id=subscription.organization_id,
                user__isnull=True,
            )
        else:
            access = access.filter(
                user_id=subscription.user_id,
                organization__isnull=True,
            )
        return access.exists()



class DeviceOwnershipHistory(models.Model):
    """تاریخچه مالکیت قانونی دستگاه؛ مستقل از قرارداد و دسترسی عملیاتی مشتری."""

    device = models.ForeignKey(
        Device, on_delete=models.CASCADE, related_name='ownership_history',
        verbose_name='دستگاه',
    )
    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.CASCADE,
        null=True, blank=True, related_name='device_ownership_history',
        verbose_name='سازمان مالک',
    )
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='device_ownership_history',
        verbose_name='مالک شخصی',
    )
    started_at = models.DateTimeField(default=timezone.now, verbose_name='شروع مالکیت')
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name='پایان مالکیت')
    reason = models.CharField(max_length=40, blank=True, verbose_name='دلیل تغییر')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'سابقه مالکیت دستگاه'
        verbose_name_plural = 'سوابق مالکیت دستگاه‌ها'
        ordering = ['-started_at', '-id']
        constraints = [
            models.CheckConstraint(
                condition=(
                    (models.Q(organization__isnull=False) & models.Q(owner_user__isnull=True))
                    | (models.Q(organization__isnull=True) & models.Q(owner_user__isnull=False))
                ),
                name='device_ownership_one_customer',
            ),
            models.UniqueConstraint(
                fields=['device'],
                condition=models.Q(ended_at__isnull=True),
                name='ownership_one_open_period',
            ),
            models.CheckConstraint(
                condition=models.Q(ended_at__isnull=True) | models.Q(ended_at__gte=models.F('started_at')),
                name='device_ownership_valid_dates',
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if bool(self.organization_id) == bool(self.owner_user_id):
            raise ValidationError('مالک دستگاه باید دقیقاً یک سازمان یا یک کاربر شخصی باشد.')
        if self.ended_at and self.ended_at < self.started_at:
            raise ValidationError({'ended_at': 'پایان مالکیت نمی‌تواند قبل از شروع آن باشد.'})


class DeviceCustomerAccessPeriod(models.Model):
    """بازه مجاز مشاهده/رصد دستگاه برای یک مشتری؛ مستقل از مالکیت و قرارداد."""

    device = models.ForeignKey(
        Device, on_delete=models.CASCADE, related_name='customer_access_periods',
        verbose_name='دستگاه',
    )
    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.CASCADE,
        null=True, blank=True, related_name='device_access_periods',
        verbose_name='سازمان',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='device_access_periods',
        verbose_name='کاربر شخصی',
    )
    subscription = models.ForeignKey(
        'organizations.Subscription', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='device_access_periods',
        verbose_name='قرارداد مرتبط',
    )
    branch = models.ForeignKey(
        'organizations.Branch', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='device_access_periods',
        verbose_name='شعبه مرتبط',
    )
    started_at = models.DateTimeField(default=timezone.now, verbose_name='شروع دسترسی')
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name='پایان دسترسی')
    reason = models.CharField(max_length=40, blank=True, verbose_name='دلیل')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'بازه دسترسی مشتری به دستگاه'
        verbose_name_plural = 'بازه‌های دسترسی مشتری به دستگاه'
        ordering = ['-started_at', '-id']
        indexes = [
            models.Index(fields=['device', 'started_at', 'ended_at']),
            models.Index(fields=['organization', 'started_at', 'ended_at']),
            models.Index(fields=['user', 'started_at', 'ended_at']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    (models.Q(organization__isnull=False) & models.Q(user__isnull=True))
                    | (models.Q(organization__isnull=True) & models.Q(user__isnull=False))
                ),
                name='device_access_one_customer',
            ),
            models.UniqueConstraint(
                fields=['device'],
                condition=models.Q(ended_at__isnull=True),
                name='device_access_one_open_period',
            ),
            models.CheckConstraint(
                condition=models.Q(ended_at__isnull=True) | models.Q(ended_at__gte=models.F('started_at')),
                name='device_access_valid_dates',
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if bool(self.organization_id) == bool(self.user_id):
            raise ValidationError('دسترسی باید دقیقاً به یک سازمان یا یک کاربر شخصی تعلق داشته باشد.')
        if self.ended_at and self.ended_at < self.started_at:
            raise ValidationError({'ended_at': 'پایان دسترسی نمی‌تواند قبل از شروع آن باشد.'})


class DeviceOperation(models.Model):
    """عملیات اتمیک روی دستگاه؛ رویدادهای چرخه عمر و تغییر قرارداد از اینجا منشعب می‌شوند."""

    OPERATION_TYPE_CHOICES = [
        ('return_for_repair', 'بازگشت برای تعمیر'),
        ('repaired', 'اتمام تعمیر'),
        ('found', 'پیدا شدن دستگاه'),
        ('disposition', 'تعیین تکلیف دستگاه'),
        ('temporary_replacement', 'جایگزینی موقت'),
        ('permanent_replacement', 'تعویض دائمی'),
        ('lost', 'گم‌شدن'),
        ('stolen', 'سرقت'),
        ('transfer_customer', 'انتقال به مشتری دیگر'),
        ('transfer_branch', 'انتقال بین شعب'),
        ('transfer_vehicle', 'انتقال بین خودروها'),
        ('retire', 'خارج کردن از چرخه استفاده'),
        ('dispose', 'امحاء'),
    ]

    operation_type = models.CharField(max_length=40, choices=OPERATION_TYPE_CHOICES, verbose_name='نوع عملیات')
    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name='operations', verbose_name='دستگاه')
    replacement_device = models.ForeignKey(
        Device, on_delete=models.PROTECT, null=True, blank=True,
        related_name='replacement_operations', verbose_name='دستگاه جایگزین'
    )
    subscription = models.ForeignKey(
        'organizations.Subscription', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='device_operations', verbose_name='قرارداد'
    )
    target_subscription = models.ForeignKey(
        'organizations.Subscription', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='target_device_operations', verbose_name='قرارداد مقصد'
    )
    target_organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='target_device_operations', verbose_name='سازمان مقصد'
    )
    target_user = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='target_device_operations', verbose_name='کاربر مقصد'
    )
    target_branch = models.ForeignKey(
        'organizations.Branch', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='target_device_operations', verbose_name='شعبه مقصد'
    )
    target_vehicle = models.ForeignKey(
        'fleet.Vehicle', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='target_device_operations', verbose_name='خودرو مقصد'
    )
    replacement_type = models.CharField(
        max_length=30,
        choices=[('temporary_repair', 'جایگزینی موقت برای تعمیر'), ('permanent_replacement', 'تعویض دائمی')],
        blank=True,
        verbose_name='نوع جایگزینی'
    )
    replacement_method = models.CharField(
        max_length=30,
        choices=[
            ('loaner', 'امانی / موقت'),
            ('sold', 'فروش به مشتری'),
            ('free_exchange', 'تعویض بدون هزینه'),
            ('paid_exchange', 'تعویض با هزینه'),
            ('warranty', 'تعویض گارانتی'),
            ('refurbished', 'دستگاه بازسازی‌شده'),
            ('other', 'سایر'),
        ],
        blank=True,
        verbose_name='نحوه تجاری جایگزینی'
    )
    outcome_action = models.CharField(
        max_length=40,
        choices=[
            ('return_customer_same_vehicle', 'بازگشت به مشتری و نصب روی همان خودرو'),
            ('return_customer_no_vehicle', 'بازگشت به مشتری بدون نصب'),
            ('sana_warehouse', 'بازگشت به انبار سانا'),
            ('customer_spare', 'تحویل به مشتری به عنوان دستگاه یدکی'),
            ('install_other_vehicle', 'نصب روی خودروی دیگر'),
            ('transfer_customer', 'انتقال به مشتری دیگر'),
            ('retire', 'خارج کردن از چرخه استفاده'),
            ('dispose', 'امحاء'),
            ('other', 'سایر'),
        ],
        blank=True,
        verbose_name='تعیین تکلیف دستگاه'
    )
    reason = models.CharField(max_length=30, blank=True, verbose_name='دلیل')
    description = models.TextField(blank=True, verbose_name='شرح')
    old_status = models.CharField(max_length=20, blank=True, verbose_name='وضعیت قبلی')
    new_status = models.CharField(max_length=20, blank=True, verbose_name='وضعیت جدید')
    performed_at = models.DateTimeField(default=timezone.now, verbose_name='زمان عملیات')
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='device_operations', verbose_name='انجام‌دهنده'
    )

    class Meta:
        verbose_name = 'عملیات دستگاه'
        verbose_name_plural = 'عملیات دستگاه'
        ordering = ['-performed_at', '-id']

    def __str__(self):
        return f'{self.device.imei} — {self.get_operation_type_display()}'
    

class DeviceBranchHistory(models.Model):
    """Historical customer branch assignment, independent from live access periods."""

    device = models.ForeignKey(
        Device, on_delete=models.CASCADE, related_name='branch_history',
        verbose_name='دستگاه',
    )
    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.PROTECT,
        related_name='device_branch_history', verbose_name='سازمان مشتری',
    )
    branch = models.ForeignKey(
        'organizations.Branch', on_delete=models.PROTECT,
        related_name='device_branch_history', verbose_name='شعبه',
    )
    subscription = models.ForeignKey(
        'organizations.Subscription', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='device_branch_history',
        verbose_name='قرارداد',
    )
    started_at = models.DateTimeField(default=timezone.now, verbose_name='شروع تخصیص شعبه')
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name='پایان تخصیص شعبه')
    reason = models.CharField(max_length=100, blank=True, verbose_name='علت')

    class Meta:
        verbose_name = 'تاریخچه شعبه دستگاه'
        verbose_name_plural = 'تاریخچه شعبه دستگاه‌ها'
        ordering = ['-started_at']
        constraints = [
            models.UniqueConstraint(
                fields=['device'],
                condition=models.Q(ended_at__isnull=True),
                name='device_one_open_branch',
            ),
            models.CheckConstraint(
                condition=models.Q(ended_at__isnull=True) | models.Q(ended_at__gte=models.F('started_at')),
                name='device_branch_valid_dates',
            ),
        ]
        indexes = [
            models.Index(fields=['device', 'started_at'], name='dev_branch_hist_idx'),
        ]

    def clean(self):
        super().clean()
        if self.branch_id and self.organization_id != self.branch.organization_id:
            raise ValidationError({'branch': 'شعبه باید متعلق به سازمان ثبت‌شده در تاریخچه باشد.'})
        if self.ended_at and self.ended_at < self.started_at:
            raise ValidationError({'ended_at': 'پایان تخصیص شعبه نمی‌تواند قبل از شروع باشد.'})

    def __str__(self):
        return f'{self.device.imei} — {self.branch.name}'

class DeviceReplacementRelation(models.Model):
    """رابطه جایگزینی بین دو دستگاه؛ تاریخچه رابطه مستقل از وضعیت فعلی دستگاه است."""

    REPLACEMENT_TYPE_CHOICES = [
        ('temporary_repair', 'جایگزینی موقت برای تعمیر'),
        ('permanent_replacement', 'تعویض دائمی'),
    ]

    source_device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name='replacement_relations_as_source',
        verbose_name='دستگاه قبلی',
    )
    replacement_device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name='replacement_relations_as_replacement',
        verbose_name='دستگاه جایگزین',
    )
    replacement_type = models.CharField(
        max_length=30,
        choices=REPLACEMENT_TYPE_CHOICES,
        verbose_name='نوع جایگزینی',
    )
    replacement_date = models.DateTimeField(default=timezone.now, verbose_name='تاریخ جایگزینی')
    returned_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ بازگشت دستگاه جایگزین موقت')
    description = models.TextField(blank=True, verbose_name='شرح')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'رابطه جایگزینی دستگاه'
        verbose_name_plural = 'روابط جایگزینی دستگاه‌ها'
        ordering = ['-replacement_date', '-id']

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.source_device_id and self.source_device_id == self.replacement_device_id:
            raise ValidationError({'replacement_device': 'دستگاه جایگزین نمی‌تواند همان دستگاه قبلی باشد.'})

    def __str__(self):
        return f'{self.source_device.imei} → {self.replacement_device.imei}'

class Driver(models.Model):
    """راننده — فقط برای سازمان‌ها"""

    POSITION_CHOICES = [
        ('driver', 'راننده'),
        ('senior', 'راننده ارشد'),
        ('supervisor', 'سرپرست رانندگان'),
    ]

    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='drivers',
        verbose_name='سازمان'
    )
    branch = models.ForeignKey(
        'organizations.Branch',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='drivers',
        verbose_name='شعبه'
    )

    # اطلاعات هویتی
    first_name = models.CharField(max_length=100, verbose_name='نام')
    last_name = models.CharField(max_length=100, verbose_name='نام خانوادگی')
    national_id = models.CharField(max_length=10, blank=True, verbose_name='کد ملی')
    mobile = models.CharField(max_length=15, verbose_name='موبایل')

    # اطلاعات استخدامی
    personnel_code = models.CharField(max_length=50, blank=True, verbose_name='کد پرسنلی')
    position = models.CharField(max_length=20, choices=POSITION_CHOICES, default='driver', verbose_name='سمت')

    # گواهینامه
    license_number = models.CharField(max_length=50, blank=True, verbose_name='شماره گواهینامه')
    license_type = models.CharField(max_length=50, blank=True, verbose_name='نوع گواهینامه')
    license_expiry = models.DateField(null=True, blank=True, verbose_name='تاریخ انقضا گواهینامه')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'راننده'
        verbose_name_plural = 'رانندگان'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

class DriverVehicleAssignment(models.Model):
    """تاریخچه تخصیص راننده به خودرو."""

    driver = models.ForeignKey(
        Driver,
        on_delete=models.CASCADE,
        related_name='vehicle_assignments',
        verbose_name='راننده',
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='driver_assignments',
        verbose_name='خودرو',
    )
    started_at = models.DateTimeField(verbose_name='شروع تخصیص')
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name='پایان تخصیص')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'تخصیص راننده به خودرو'
        verbose_name_plural = 'تخصیص‌های راننده به خودرو'
        ordering = ['-started_at', '-id']
        indexes = [
            models.Index(fields=['driver', 'started_at', 'ended_at']),
            models.Index(fields=['vehicle', 'started_at', 'ended_at']),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.ended_at and self.ended_at <= self.started_at:
            raise ValidationError({'ended_at': 'پایان تخصیص باید بعد از شروع تخصیص باشد.'})

        if self.driver.organization_id != self.vehicle.organization_id:
            raise ValidationError({'vehicle': 'راننده و خودرو باید متعلق به یک سازمان باشند.'})

        if self.driver.branch_id and self.vehicle.branch_id and self.driver.branch_id != self.vehicle.branch_id:
            raise ValidationError({'vehicle': 'شعبه راننده و خودرو باید یکسان باشد.'})

        overlap = DriverVehicleAssignment.objects.filter(
            vehicle=self.vehicle,
        ).exclude(pk=self.pk)

        if self.ended_at:
            overlap = overlap.filter(
                started_at__lt=self.ended_at,
            ).filter(
                models.Q(ended_at__isnull=True) | models.Q(ended_at__gt=self.started_at)
            )
        else:
            overlap = overlap.filter(
                models.Q(ended_at__isnull=True) | models.Q(ended_at__gt=self.started_at)
            )
        if overlap.exists():
            raise ValidationError({'vehicle': 'این بازه زمانی با تخصیص دیگری به این خودرو تداخل دارد.'})

    def __str__(self):
        return f'{self.driver} → {self.vehicle}'


class DeviceLifecycleEvent(models.Model):
    """رویدادهای غیرقابل‌حذف چرخه عمر دستگاه."""

    EVENT_TYPE_CHOICES = [
        ('received', 'دریافت در سانا'),
        ('sold', 'فروش'),
        ('assigned_to_contract', 'اتصال به قرارداد'),
        ('removed_from_contract', 'خروج از قرارداد'),
        ('returned', 'بازگشت به سانا'),
        ('sent_to_repair', 'ارسال برای تعمیر'),
        ('repaired', 'اتمام تعمیر'),
        ('replaced', 'تعویض'),
        ('transferred', 'انتقال'),
        ('lost', 'گم‌شدن'),
        ('found', 'پیدا شدن'),
        ('disposition', 'تعیین تکلیف'),
        ('stolen', 'سرقت'),
        ('retired', 'خروج از چرخه استفاده'),
        ('disposed', 'امحاء'),
    ]

    RETURN_REASON_CHOICES = [
        ('repair', 'تعمیر'),
        ('replacement', 'تعویض'),
        ('contract_termination', 'پایان قرارداد'),
        ('customer_return', 'مرجوعی مشتری'),
        ('upgrade', 'ارتقاء'),
        ('defective', 'خرابی'),
        ('other', 'سایر'),
    ]

    device = models.ForeignKey(
        Device, on_delete=models.CASCADE, related_name='lifecycle_events', verbose_name='دستگاه'
    )
    device_operation = models.ForeignKey(
        'fleet.DeviceOperation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lifecycle_events', verbose_name='عملیات دستگاه'
    )
    event_type = models.CharField(max_length=30, choices=EVENT_TYPE_CHOICES, verbose_name='نوع رویداد')
    event_date = models.DateTimeField(default=timezone.now, verbose_name='تاریخ رویداد')
    subscription = models.ForeignKey(
        'organizations.Subscription', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='device_lifecycle_events', verbose_name='قرارداد'
    )
    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='device_lifecycle_events', verbose_name='سازمان'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='device_lifecycle_events', verbose_name='کاربر'
    )
    vehicle = models.ForeignKey(
        'fleet.Vehicle', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='device_lifecycle_events', verbose_name='خودرو'
    )
    branch = models.ForeignKey(
        'organizations.Branch', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='device_lifecycle_events', verbose_name='شعبه'
    )
    reason = models.CharField(max_length=30, choices=RETURN_REASON_CHOICES, blank=True, verbose_name='دلیل')
    description = models.TextField(blank=True, verbose_name='شرح')
    previous_status = models.CharField(max_length=20, blank=True, verbose_name='وضعیت قبلی')
    new_status = models.CharField(max_length=20, blank=True, verbose_name='وضعیت جدید')
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='performed_device_lifecycle_events', verbose_name='انجام‌دهنده'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'رویداد چرخه عمر دستگاه'
        verbose_name_plural = 'رویدادهای چرخه عمر دستگاه'
        ordering = ['-event_date', '-id']

    def __str__(self):
        return f'{self.device.imei} — {self.get_event_type_display()}'



class DeviceAlertState(models.Model):
    """Unified per-user notification state; GPS telemetry remains authoritative in Traccar."""
    STATUS_CHOICES = [
        ('unread', 'خوانده‌نشده'),
        ('read', 'خوانده‌شده'),
        ('reviewed', 'بررسی‌شده'),
        ('resolved', 'رفع‌شده'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='device_alert_states',
        verbose_name='کاربر',
    )
    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='alert_states',
        verbose_name='دستگاه',
    )
    event_key = models.CharField(max_length=200, verbose_name='شناسه یکتای اعلان')
    notification_type = models.CharField(max_length=64, default='gps', verbose_name='دسته اعلان')
    traccar_event_id = models.CharField(max_length=64, blank=True, default='', verbose_name='شناسه رویداد Traccar')
    event_type = models.CharField(max_length=64, verbose_name='نوع رویداد')
    event_time = models.DateTimeField(verbose_name='زمان رویداد')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unread')
    read_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'وضعیت اعلان'
        verbose_name_plural = 'وضعیت اعلان‌ها'
        ordering = ['-event_time', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'event_key'],
                name='fleet_alert_user_event_key_uniq',
            ),
            models.UniqueConstraint(
                fields=['user', 'device', 'traccar_event_id'],
                name='fleet_alert_user_device_event_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'status', 'event_time'], name='fleet_alert_user_status_idx'),
            models.Index(fields=['device', 'event_type', 'event_time'], name='fleet_alert_device_type_idx'),
        ]

class PersonalAlertPreference(models.Model):
    """Per-user filters for Traccar events shown in the personal alert center."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='personal_alert_preference',
        verbose_name='کاربر',
    )
    disabled_event_types = models.JSONField(default=list, blank=True, verbose_name='انواع هشدار غیرفعال')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'تنظیمات هشدار مشتری شخصی'
        verbose_name_plural = 'تنظیمات هشدار مشتریان شخصی'

    def __str__(self):
        return f'تنظیمات هشدارهای {self.user}'
