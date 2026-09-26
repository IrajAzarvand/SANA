from django.db import models
from django.utils import timezone


class Organization(models.Model):
    """شرکت / سازمان مشتری"""

    STATUS_CHOICES = [
        ('active', 'فعال'),
        ('inactive', 'غیرفعال'),
        ('suspended', 'تعلیق‌شده'),
    ]

    name = models.CharField(max_length=200, verbose_name='نام سازمان')
    code = models.CharField(max_length=50, unique=True, verbose_name='کد سازمان')
    registration_number = models.CharField(max_length=50, blank=True, verbose_name='شماره ثبت')
    economy_code = models.CharField(max_length=50, blank=True, verbose_name='کد اقتصادی')

    phone = models.CharField(max_length=20, blank=True, verbose_name='تلفن')
    email = models.EmailField(blank=True, verbose_name='ایمیل')
    address = models.TextField(blank=True, verbose_name='آدرس')
    website = models.URLField(blank=True, verbose_name='وبسایت')
    logo = models.ImageField(upload_to='organizations/logos/', null=True, blank=True, verbose_name='لوگو')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name='وضعیت')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'سازمان'
        verbose_name_plural = 'سازمان‌ها'
        ordering = ['name']

    def __str__(self):
        return self.name


class Branch(models.Model):
    """شعبه سازمان"""

    STATUS_CHOICES = [
        ('active', 'فعال'),
        ('inactive', 'غیرفعال'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='branches',
        verbose_name='سازمان'
    )
    name = models.CharField(max_length=200, verbose_name='نام شعبه')
    code = models.CharField(max_length=50, verbose_name='کد شعبه')

    phone = models.CharField(max_length=20, blank=True, verbose_name='تلفن')
    address = models.TextField(blank=True, verbose_name='آدرس')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name='وضعیت')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'شعبه'
        verbose_name_plural = 'شعبه‌ها'
        ordering = ['organization', 'name']
        unique_together = [['organization', 'code']]

    def __str__(self):
        return f'{self.organization.name} — {self.name}'


class Subscription(models.Model):
    """قرارداد / اشتراک سرویس"""

    CUSTOMER_TYPE_CHOICES = [
        ('organization', 'سازمانی'),
        ('personal', 'شخصی'),
    ]

    STATUS_CHOICES = [
        ('active', 'فعال'),
        ('suspended', 'تعلیق‌شده'),
        ('expired', 'منقضی'),
        ('cancelled', 'لغو‌شده'),
    ]

    contract_number = models.CharField(
        max_length=50, unique=True, verbose_name='شماره قرارداد'
    )
    customer_type = models.CharField(
        max_length=20, choices=CUSTOMER_TYPE_CHOICES,
        default='organization', verbose_name='نوع مشتری'
    )

    # مشتری — یکی از این دو پر می‌شود
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='subscriptions',
        verbose_name='سازمان'
    )
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='personal_subscriptions',
        verbose_name='کاربر شخصی'
    )

    # تاریخ‌ها
    start_date = models.DateField(verbose_name='تاریخ شروع قرارداد')
    end_date = models.DateField(verbose_name='تاریخ پایان قرارداد')

    # مالی
    price = models.DecimalField(
        max_digits=15, decimal_places=0,
        default=0, verbose_name='مبلغ کل (ریال)'
    )

    # وضعیت
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default='active', verbose_name='وضعیت'
    )

    notes = models.TextField(blank=True, verbose_name='یادداشت')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    
    class Meta:
        verbose_name = 'قرارداد'
        verbose_name_plural = 'قراردادها'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.contract_number} — {self.get_customer_name()}'

    def get_customer_name(self):
        if self.organization:
            return self.organization.name
        if self.user:
            return self.user.full_name or self.user.username
        return '—'

    @property
    def computed_status(self):
        """
        وضعیت واقعی قرارداد بر اساس تاریخ
        
        - اگه دستی لغو یا تعلیق شده، همون رو برگردون
        - اگه منقضی شده، expired
        - اگه هنوز شروع نشده، pending
        - در غیر این صورت، active
        """
        today = timezone.now().date()
        
        # وضعیت‌های دستی که تاریخ مهم نیست
        if self.status in ['cancelled', 'suspended']:
            return self.status
        
        # اگه منقضی شده (فردا به بعد)
        if self.end_date < today:
            return 'expired'
        
        # اگه هنوز شروع نشده
        if self.start_date > today:
            return 'pending'
        
        # در غیر این صورت، فعال
        return 'active'

    @property
    def is_active(self):
        """آیا قرارداد در حال حاضر فعاله؟"""
        return self.computed_status == 'active'

    @property
    def days_until_expiry(self):
        """چند روز تا پایان قرارداد مونده؟"""
        today = timezone.now().date()
        return (self.end_date - today).days

    @property
    def is_expiring_soon(self):
        """آیا بین ۱ تا ۳۰ روز تا پایان مونده؟"""
        return 1 <= self.days_until_expiry <= 30
    @property
    def active_device_count(self):
        """تعداد دستگاه‌های فعال این قرارداد"""
        return self.subscription_devices.filter(unassigned_at__isnull=True).count()

    def recalculate_price(self):
        """محاسبه‌ی مجدد مبلغ از مجموع پرداخت‌ها"""
        total = self.payments.aggregate(
            total=models.Sum('amount')
        )['total'] or 0
        self.price = total
        self.save(update_fields=['price'])

    def recalculate_end_date(self):
        """محاسبه‌ی مجدد end_date از آخرین دستگاه فعال"""
        latest = self.subscription_devices.filter(
            unassigned_at__isnull=True
        ).order_by('-end_date').first()

        if latest:
            self.end_date = latest.end_date
            self.save(update_fields=['end_date'])

    @classmethod
    def generate_contract_number(cls, customer_type='organization'):
        """
        تولید شماره قرارداد یکتا با فرمت: ORG-1405-0001
        - ORG: سازمانی، PRS: شخصی
        - 1405: سال شمسی
        - 0001: شماره ترتیبی (4 رقمی، صفر پر شده)
        """
        import jdatetime
        
        prefix = 'ORG' if customer_type == 'organization' else 'PRS'
        
        # سال شمسی
        today = jdatetime.date.today()
        jalali_year = today.year
        
        # پیدا کردن بیشترین شماره موجود برای این پیشوند و سال
        pattern = f'{prefix}-{jalali_year}-'
        last = cls.objects.filter(
            contract_number__startswith=pattern
        ).order_by('-contract_number').first()
        
        if last:
            # استخراج شماره ترتیبی از آخرین قرارداد
            try:
                last_num = int(last.contract_number.split('-')[-1])
                next_num = last_num + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1
        
        # فرمت 4 رقمی
        return f'{prefix}-{jalali_year}-{next_num:04d}'

class SubscriptionDevice(models.Model):
    """اتصال تاریخی دستگاه به قرارداد"""

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='subscription_devices',
        verbose_name='قرارداد'
    )
    device = models.ForeignKey(
        'fleet.Device',
        on_delete=models.CASCADE,
        related_name='subscription_links',
        verbose_name='دستگاه'
    )

    # تاریخ‌های خود دستگاه
    start_date = models.DateField(verbose_name='تاریخ شروع دستگاه')
    end_date = models.DateField(verbose_name='تاریخ پایان دستگاه')

    # تاریخ‌های فنی
    assigned_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ اتصال')
    unassigned_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ جدا شدن')

    class Meta:
        verbose_name = 'دستگاه قرارداد'
        verbose_name_plural = 'دستگاه‌های قرارداد'
        ordering = ['-assigned_at']

    def __str__(self):
        return f'{self.device.imei} → {self.subscription.contract_number}'

    @property
    def is_active(self):
        """آیا این دستگاه در حال حاضر فعاله؟"""
        today = timezone.now().date()
        return (
            self.unassigned_at is None and
            self.start_date <= today <= self.end_date
        )

    @property
    def is_expired(self):
        """آیا منقضی شده؟"""
        return self.end_date < timezone.now().date()

    @property
    def days_until_expiry(self):
        """چند روز تا پایان این دستگاه مونده؟"""
        today = timezone.now().date()
        return (self.end_date - today).days

    def save(self, *args, **kwargs):
        # اگه رکورد جدید، رکوردهای فعال قبلی همین دستگاه رو ببند
        if self.pk is None:
            SubscriptionDevice.objects.filter(
                device=self.device,
                unassigned_at__isnull=True,
            ).update(unassigned_at=timezone.now())

        super().save(*args, **kwargs)

        # بعد از ذخیره، end_date قرارداد رو آپدیت کن
        self.subscription.recalculate_end_date()


class SubscriptionPayment(models.Model):
    """تاریخچه پرداخت‌های قرارداد"""

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='قرارداد'
    )

    amount = models.DecimalField(
        max_digits=15, decimal_places=0,
        verbose_name='مبلغ (ریال)'
    )
    payment_date = models.DateField(verbose_name='تاریخ پرداخت')

    device_count = models.IntegerField(
        default=0, verbose_name='تعداد دستگاه این پرداخت'
    )
    description = models.TextField(blank=True, verbose_name='توضیحات')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'پرداخت'
        verbose_name_plural = 'پرداخت‌ها'
        ordering = ['-payment_date']

    def __str__(self):
        return f'{self.subscription.contract_number} — {self.amount}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # بعد از ذخیره، price قرارداد رو آپدیت کن
        self.subscription.recalculate_price()


class SubscriptionRenewal(models.Model):
    """تاریخچه تمدیدهای قرارداد"""

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='renewals',
        verbose_name='قرارداد'
    )

    old_end_date = models.DateField(verbose_name='تاریخ پایان قبلی')
    new_end_date = models.DateField(verbose_name='تاریخ پایان جدید')

    notes = models.TextField(blank=True, verbose_name='یادداشت تمدید')

    renewed_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ تمدید')
    renewed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='renewals',
        verbose_name='تمدیدکننده'
    )

    class Meta:
        verbose_name = 'تمدید قرارداد'
        verbose_name_plural = 'تمدیدهای قرارداد'
        ordering = ['-renewed_at']

    def __str__(self):
        return f'{self.subscription.contract_number} — {self.old_end_date} → {self.new_end_date}'