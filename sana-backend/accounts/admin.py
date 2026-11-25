from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserSession


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'full_name', 'role', 'account_type', 'organization', 'branch', 'is_active']
    list_filter = ['role', 'account_type', 'is_active', 'organization']
    search_fields = ['username', 'first_name', 'last_name', 'email', 'mobile']
    ordering = ['-date_joined']

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        if request.user.pk == obj.pk and (
            obj.role != 'site_admin' or not obj.is_active
        ):
            raise ValidationError(
                'امکان تنزل نقش یا غیرفعال‌سازی حساب مدیر سایتِ واردشده وجود ندارد.'
            )

        previous_access_state = None
        if change:
            previous = User.objects.get(pk=obj.pk)
            previous_access_state = (
                previous.role,
                previous.account_type,
                previous.organization_id,
                previous.branch_id,
                previous.is_active,
            )
            if previous.role == 'site_admin' and previous.is_active and (
                obj.role != 'site_admin' or not obj.is_active
            ):
                # Lock active admins in a consistent order to serialize concurrent
                # demotion/deactivation attempts without creating lock-order cycles.
                active_admin_ids = list(
                    User.objects.select_for_update().filter(
                        role='site_admin', is_active=True
                    ).order_by('pk').values_list('pk', flat=True)
                )
                if obj.pk in active_admin_ids and len(active_admin_ids) <= 1:
                    raise ValidationError(
                        'حداقل یک مدیر سایت فعال باید در سامانه باقی بماند.'
                    )

        obj.is_staff = obj.role == 'site_admin'
        obj.is_superuser = obj.role == 'site_admin'
        super().save_model(request, obj, form, change)

        current_access_state = (
            obj.role,
            obj.account_type,
            obj.organization_id,
            obj.branch_id,
            obj.is_active,
        )
        if previous_access_state is not None and current_access_state != previous_access_state:
            UserSession.objects.filter(
                user=obj,
                revoked_at__isnull=True,
            ).update(revoked_at=timezone.now())

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('اطلاعات شخصی', {'fields': ('first_name', 'last_name', 'email', 'mobile', 'national_id')}),
        ('نقش و دسترسی', {'fields': ('account_type', 'role', 'organization', 'branch', 'is_active', 'is_staff', 'is_superuser')}),
        ('تاریخ‌ها', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'role', 'account_type', 'organization', 'branch'),
        }),
    )

@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at', 'last_activity_at', 'expires_at', 'revoked_at', 'ip_address']
    list_filter = ['revoked_at', 'created_at']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'ip_address']
    readonly_fields = [
        'id', 'user', 'created_at', 'last_activity_at', 'expires_at',
        'revoked_at', 'current_refresh_jti', 'ip_address', 'user_agent',
    ]
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
