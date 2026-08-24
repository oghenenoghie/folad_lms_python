from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.core.admin import TenantAdminMixin

from .forms import UserChangeForm, UserCreationForm
from .models import FailedLoginAttempt, LoginHistory, Permission, Role, RolePermission, User, UserRole


@admin.register(User)
class UserAdmin(TenantAdminMixin, DjangoUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    ordering = ["email"]
    list_display = ["email", "first_name", "last_name", "organization", "is_staff", "is_active"]
    search_fields = ["email", "first_name", "last_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("first_name", "last_name", "organization")}),
        ("MFA", {"fields": ("mfa_enabled", "mfa_secret")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser")}),
    )
    add_fieldsets = (
        (None, {"fields": ("email", "first_name", "last_name", "organization", "password1", "password2")}),
    )
    filter_horizontal = ()
    list_filter = ["is_staff", "is_active", "organization"]


admin.site.register(Permission)
admin.site.register(Role)
admin.site.register(RolePermission)
admin.site.register(UserRole)
admin.site.register(FailedLoginAttempt)


@admin.register(LoginHistory)
class LoginHistoryAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["user", "organization", "ip_address", "success", "created_at"]
    list_filter = ["success", "organization"]
    search_fields = ["user__email", "ip_address"]
