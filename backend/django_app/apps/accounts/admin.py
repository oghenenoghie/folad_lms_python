from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm

from apps.core.admin import TenantAdminMixin

from .forms import UserChangeForm, UserCreationForm
from .models import FailedLoginAttempt, LoginHistory, Permission, Role, RolePermission, User, UserRole


@admin.register(User)
class UserAdmin(TenantAdminMixin, DjangoUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
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
    autocomplete_fields = ["organization"]


@admin.register(Permission)
class PermissionAdmin(ModelAdmin):
    list_display = ["code", "module", "action"]
    search_fields = ["code", "module", "action"]
    list_filter = ["module"]


@admin.register(Role)
class RoleAdmin(ModelAdmin):
    list_display = ["name", "label", "is_system", "organization"]
    search_fields = ["name", "label"]
    list_filter = ["is_system", "organization"]
    autocomplete_fields = ["organization"]


@admin.register(RolePermission)
class RolePermissionAdmin(ModelAdmin):
    list_display = ["role", "permission"]
    autocomplete_fields = ["role", "permission"]


@admin.register(UserRole)
class UserRoleAdmin(ModelAdmin):
    list_display = ["user", "role", "granted_by", "granted_at"]
    autocomplete_fields = ["user", "role", "granted_by"]


admin.site.register(FailedLoginAttempt)


@admin.register(LoginHistory)
class LoginHistoryAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["user", "organization", "ip_address", "success", "created_at"]
    list_filter = ["success", "organization"]
    search_fields = ["user__email", "ip_address"]
    autocomplete_fields = ["user", "organization"]
