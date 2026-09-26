from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'full_name', 'role', 'account_type', 'organization', 'branch', 'is_active']
    list_filter = ['role', 'account_type', 'is_active', 'organization']
    search_fields = ['username', 'first_name', 'last_name', 'email', 'mobile']
    ordering = ['-date_joined']

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