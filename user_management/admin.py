from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, UserLoginLog, UserOperationLog


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        'username', 'email', 'real_name', 'role', 'status',
        'department', 'is_active', 'date_joined', 'last_login'
    ]
    list_filter = ['role', 'status', 'is_staff', 'is_active', 'date_joined']
    search_fields = ['username', 'email', 'real_name', 'phone']
    ordering = ['-date_joined']
    date_hierarchy = 'date_joined'

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('个人信息', {'fields': ('real_name', 'email', 'phone', 'avatar', 'bio')}),
        ('组织信息', {'fields': ('role', 'department', 'status')}),
        ('权限', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('重要日期', {'fields': ('last_login', 'date_joined', 'updated_at')}),
        ('安全信息', {'fields': ('last_login_ip',)}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'role', 'status'),
        }),
    )

    readonly_fields = ['last_login', 'date_joined', 'updated_at', 'last_login_ip']

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser:
            # 非超级管理员不能修改 is_superuser 和 groups
            if 'is_superuser' in form.base_fields:
                form.base_fields['is_superuser'].disabled = True
        return form


@admin.register(UserLoginLog)
class UserLoginLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'ip_address', 'login_type', 'status', 'created_at']
    list_filter = ['status', 'login_type', 'created_at']
    search_fields = ['user__username', 'ip_address']
    readonly_fields = [
        'user', 'ip_address', 'user_agent',
        'login_type', 'status', 'fail_reason', 'created_at'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(UserOperationLog)
class UserOperationLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'resource_type', 'username_display', 'ip_address', 'created_at']
    list_filter = ['action', 'resource_type', 'created_at']
    search_fields = ['user__username', 'action', 'resource_type']
    readonly_fields = [
        'user', 'action', 'resource_type', 'resource_id',
        'detail', 'ip_address', 'created_at'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']

    def username_display(self, obj):
        return obj.user.username if obj.user else '-'
    username_display.short_description = '操作用户'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
