from django.db import models
from django.conf import settings


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
        """آیا توی انباره؟"""
        return self.active_subscription_link is None

    @property
    def is_data_active(self):
        """آیا داده‌ی این دستگاه باید دریافت بشه؟"""
        link = self.active_subscription_link
        if not link:
            return False
        return link.is_active

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