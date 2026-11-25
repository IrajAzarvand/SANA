import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('نام کاربری الزامی است')
        # Keep role/account type and Django's independent admin flags aligned
        # across every user-creation path, not only API serializers.
        role_account_types = {
            'site_admin': 'admin',
            'main_user': 'organization',
            'branch_manager': 'organization',
            'personal_user': 'personal',
        }
        role = extra_fields.get('role', 'personal_user')
        expected_account_type = role_account_types.get(role)
        if expected_account_type:
            account_type = extra_fields.get('account_type', expected_account_type)
            if account_type != expected_account_type:
                raise ValueError('Account type does not match the application role')
            extra_fields['account_type'] = expected_account_type

        is_site_admin = role == 'site_admin'
        extra_fields['is_staff'] = is_site_admin
        extra_fields['is_superuser'] = is_site_admin
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        if extra_fields.get('role', 'site_admin') != 'site_admin':
            raise ValueError('Superusers must have the site_admin role')
        if extra_fields.get('account_type', 'admin') != 'admin':
            raise ValueError('Superusers must have the admin account type')
        if extra_fields.get('is_staff', True) is not True:
            raise ValueError('Superusers must have is_staff=True')
        if extra_fields.get('is_superuser', True) is not True:
            raise ValueError('Superusers must have is_superuser=True')
        extra_fields['is_staff'] = True
        extra_fields['is_superuser'] = True
        extra_fields['role'] = 'site_admin'
        extra_fields['account_type'] = 'admin'
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
    archived_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان بایگانی')
    archived_by = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='archived_users', verbose_name='بایگانی‌کننده',
    )
    archived_was_active = models.BooleanField(default=True, verbose_name='وضعیت فعال پیش از بایگانی')
    is_staff = models.BooleanField(default=False, verbose_name='دسترسی ادمین')
    date_joined = models.DateTimeField(default=timezone.now, verbose_name='تاریخ عضویت')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین به‌روزرسانی')
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
        today = timezone.localdate()

        if self.is_site_admin:
            return None

        # کاربران شعبه نیز باید قرارداد سازمان مادر را دنبال کنند،
        # حتی اگر فیلد organization روی حسابشان خالی باشد.
        organization = self.organization if self.organization_id else (
            self.branch.organization if self.branch_id else None
        )

        # فیلتر بر اساس وضعیت ذخیره‌شده و تاریخ‌های قرارداد
        if organization:
            return organization.subscriptions.filter(
                status='active',  # نه suspended/cancelled
                start_date__lte=today,  # شروع شده
                end_date__gte=today,  # تاریخ پایان امروز هم معتبر است
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
        """آیا سازمان مرتبط با حساب کاربر فعاله؟"""
        organization = self.organization if self.organization_id else (
            self.branch.organization if self.branch_id else None
        )
        if not organization:
            return True
        return organization.status == 'active'

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


class UserSession(models.Model):
    """Server-side lifecycle record for one authenticated browser/device session."""

    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='auth_sessions',
        verbose_name='کاربر',
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='زمان ورود')
    last_activity_at = models.DateTimeField(default=timezone.now, verbose_name='آخرین فعالیت')
    expires_at = models.DateTimeField(verbose_name='انقضای نشست')
    revoked_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان ابطال')
    current_refresh_jti = models.CharField(max_length=255, blank=True, verbose_name='شناسه Refresh فعلی')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP ورود')
    user_agent = models.CharField(max_length=512, blank=True, verbose_name='مرورگر/دستگاه')

    class Meta:
        verbose_name = 'نشست ورود'
        verbose_name_plural = 'نشست‌های ورود'
        indexes = [
            models.Index(fields=['user', 'revoked_at'], name='accounts_sess_user_rev_idx'),
            models.Index(fields=['expires_at'], name='accounts_sess_expires_idx'),
        ]

    @property
    def is_active(self):
        now = timezone.now()
        return (
            self.revoked_at is None
            and self.expires_at > now
            and self.last_activity_at > now - timedelta(minutes=30)
        )
