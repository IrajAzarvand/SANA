from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('نام کاربری الزامی است')
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'site_admin')
        extra_fields.setdefault('account_type', 'admin')
        return self.create_user(username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    # انواع حساب
    ACCOUNT_TYPE_CHOICES = [
        ('admin', 'ادمین کل سایت'),
        ('organization', 'سازمانی'),
        ('personal', 'شخصی'),
    ]

    # نقش‌ها
    ROLE_CHOICES = [
        ('site_admin', 'ادمین کل سایت'),
        ('main_user', 'مدیر شرکت'),
        ('branch_manager', 'مدیر شعبه'),
        ('personal_user', 'کاربر شخصی'),
    ]

    # اطلاعات پایه
    username = models.CharField(max_length=150, unique=True, verbose_name='نام کاربری')
    email = models.EmailField(blank=True, null=True, verbose_name='ایمیل')
    mobile = models.CharField(max_length=20, blank=True, null=True, verbose_name='موبایل')
    first_name = models.CharField(max_length=100, blank=True, verbose_name='نام')
    last_name = models.CharField(max_length=100, blank=True, verbose_name='نام خانوادگی')
    national_id = models.CharField(max_length=20, blank=True, null=True, verbose_name='کد ملی')
    address = models.TextField(blank=True, verbose_name='آدرس')

    # نوع حساب و نقش
    account_type = models.CharField(
        max_length=20, choices=ACCOUNT_TYPE_CHOICES, default='personal', verbose_name='نوع حساب'
    )
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES, default='personal_user', verbose_name='نقش'
    )

    # ارتباط با سازمان و شعبه (اختیاری - برای کاربران سازمانی)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='users',
        verbose_name='سازمان'
    )
    branch = models.ForeignKey(
        'organizations.Branch',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='users',
        verbose_name='شعبه'
    )

    # دسترسی‌ها
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    is_staff = models.BooleanField(default=False, verbose_name='دسترسی ادمین')
    date_joined = models.DateTimeField(default=timezone.now, verbose_name='تاریخ عضویت')
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'کاربر'
        verbose_name_plural = 'کاربران'

    def __str__(self):
        full_name = f'{self.first_name} {self.last_name}'.strip()
        return full_name or self.username

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def is_site_admin(self):
        return self.role == 'site_admin'

    @property
    def is_main_user(self):
        return self.role == 'main_user'

    @property
    def is_branch_manager(self):
        return self.role == 'branch_manager'

    @property
    def is_personal_user(self):
        return self.role == 'personal_user'

    # ═══════════════════════════════════════════════
    # منطق اشتراک و دسترسی
    # ═══════════════════════════════════════════════

    @property
    def active_subscription(self):
        """آخرین قرارداد فعال کاربر یا سازمانش"""
        today = timezone.now().date()

        if self.is_site_admin:
            return None

        # فیلتر بر اساس computed_status
        # چون computed_status توی دیتابیس نیست، از تاریخ استفاده می‌کنیم
        if self.organization_id:
            return self.organization.subscriptions.filter(
                status='active',  # نه suspended/cancelled
                start_date__lte=today,  # شروع شده
                end_date__gte=today,  # منقضی نشده
            ).order_by('-end_date').first()

        if self.account_type == 'personal':
            return self.personal_subscriptions.filter(
                status='active',
                start_date__lte=today,
                end_date__gte=today,
            ).order_by('-end_date').first()

        return None

    @property
    def has_active_subscription(self):
        """آیا اشتراک فعال داره؟"""
        if self.is_site_admin:
            return True
        return self.active_subscription is not None

    @property
    def is_organization_active(self):
        """آیا سازمان کاربر فعاله؟"""
        if not self.organization_id:
            return True
        return self.organization.status == 'active'

    @property
    def can_login(self):
        """
        آیا کاربر می‌تونه لاگین کنه؟
        چک می‌کنه:
        1. is_active (کاربر)
        2. Organization.status (اگه سازمانی)
        3. قرارداد فعال
        """
        if not self.is_active:
            return False

        if self.is_site_admin:
            return True

        if not self.is_organization_active:
            return False

        return self.has_active_subscription

    @property
    def can_receive_data(self):
        """آیا دستگاه‌هاش می‌تونن داده بفرستن؟"""
        return self.can_login

    @property
    def can_write(self):
        """آیا می‌تونه عملیات جدید انجام بده؟"""
        return self.can_login