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
    """مدل دستگاه GPS"""
    manufacturer = models.CharField(max_length=100, verbose_name='سازنده')
    name = models.CharField(max_length=100, verbose_name='نام مدل')
    code = models.CharField(max_length=50, verbose_name='کد مدل')
    protocol = models.CharField(max_length=50, verbose_name='پروتکل')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'مدل دستگاه'
        verbose_name_plural = 'مدل‌های دستگاه'
        ordering = ['manufacturer', 'name']

    def __str__(self):
        return f'{self.manufacturer} — {self.name}'


class Device(models.Model):
    """دستگاه GPS"""

    MANAGEMENT_STATUS_CHOICES = [
        ('warehouse', 'در انبار'),
        ('sold', 'فروخته شده'),
        ('installed', 'نصب شده'),
        ('active', 'فعال'),
        ('faulty', 'خراب'),
        ('lost', 'گمشده'),
        ('stolen', 'سرقت شده'),
        ('disconnected', 'قطع سرویس'),
        ('retired', 'بازنشسته'),
        ('disposed', 'امحاء شده'),
    ]

    imei = models.CharField(max_length=20, unique=True, verbose_name='IMEI')
    device_model = models.ForeignKey(
        DeviceModel,
        on_delete=models.PROTECT,
        related_name='devices',
        verbose_name='مدل دستگاه'
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
        return link.is_active


class DeviceOperation(models.Model):
    """عملیات اتمیک روی دستگاه؛ رویدادهای چرخه عمر و تغییر قرارداد از اینجا منشعب می‌شوند."""

    OPERATION_TYPE_CHOICES = [
        ('return_for_repair', 'بازگشت برای تعمیر'),
        ('repaired', 'اتمام تعمیر'),
        ('temporary_replacement', 'جایگزینی موقت'),
        ('permanent_replacement', 'تعویض دائمی'),
        ('lost', 'گم‌شدن'),
        ('stolen', 'سرقت'),
        ('transfer_customer', 'انتقال به مشتری دیگر'),
        ('transfer_branch', 'انتقال بین شعب'),
        ('transfer_vehicle', 'انتقال بین خودروها'),
        ('retire', 'بازنشستگی'),
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
        choices=DeviceReplacementRelation.REPLACEMENT_TYPE_CHOICES,
        blank=True,
        verbose_name='نوع جایگزینی'
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
        ('stolen', 'سرقت'),
        ('retired', 'بازنشستگی'),
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
