from django.contrib.auth.base_user import AbstractBaseUser
from django.db import models

from apps.core.models import BaseModel, TimestampedModel, UUIDPublicIdModel
from apps.tenancy.managers import TenantManager

from .managers import UserManager


class User(AbstractBaseUser, BaseModel):
    """§8 ARCHITECTURE.md. Nullable `organization` supports platform-level
    (SUPER_ADMIN) accounts that operate across tenants; every other user
    belongs to exactly one organization for the lifetime of the account.
    """

    organization = models.ForeignKey(
        "tenancy.Organization",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="users",
    )
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    # TOTP MFA (§8: required for admin-tier roles by policy). The secret is
    # sensitive at rest; production deployments should encrypt this column
    # (e.g. via a KMS-backed field) — plaintext here is an M2-scope tradeoff.
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=32, blank=True, default="")

    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "accounts_user"

    def __str__(self) -> str:
        return self.email

    # Django Admin (contrib.admin) calls these directly on the user object
    # (has_module_permission() -> request.user.has_module_perms(...), etc.),
    # and they don't exist unless a model inherits PermissionsMixin — which
    # this model deliberately doesn't, since that would pull in Django's
    # own Group/Permission tables alongside this app's own RBAC (Role,
    # Permission, UserRole — see apps/accounts/permissions.py), duplicating
    # the permission system for no benefit. Django Admin here is the
    # platform ops console (§11 ARCHITECTURE.md), not the general app UI —
    # every other role's authorization goes through the API's RBAC
    # (require_permission()), so it's correct for Admin access to be
    # is_superuser-gated only.
    def has_perm(self, perm, obj=None) -> bool:
        return self.is_active and self.is_superuser

    def has_perms(self, perm_list, obj=None) -> bool:
        return self.is_active and self.is_superuser

    def has_module_perms(self, app_label) -> bool:
        return self.is_active and self.is_superuser


class Permission(models.Model):
    """A `module.action` grant, e.g. `students.view` (§8 ARCHITECTURE.md)."""

    code = models.CharField(max_length=100, unique=True)
    module = models.CharField(max_length=50)
    action = models.CharField(max_length=50)
    description = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "accounts_permission"
        ordering = ["module", "action"]

    def __str__(self) -> str:
        return self.code


class Role(UUIDPublicIdModel):
    """A named bundle of permissions. `is_system` roles ship with the
    platform; non-system roles are the CUSTOM_ROLE composition a school
    can build for itself (§8 ARCHITECTURE.md). Carries `public_id` (unlike
    Permission/RolePermission/UserRole) because it's the one RBAC entity
    addressed directly by the Users & Roles admin API — the only external
    identifier this codebase ever exposes (see core/models.py)."""

    name = models.CharField(max_length=100, unique=True)
    label = models.CharField(max_length=150)
    is_system = models.BooleanField(default=True)
    organization = models.ForeignKey(
        "tenancy.Organization",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="custom_roles",
        help_text="Set only for a school's own CUSTOM_ROLE; null for system roles.",
    )
    permissions = models.ManyToManyField(Permission, through="RolePermission", related_name="roles")

    class Meta:
        db_table = "accounts_role"

    def __str__(self) -> str:
        return self.name


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        db_table = "accounts_role_permission"
        constraints = [
            models.UniqueConstraint(fields=["role", "permission"], name="uq_role_permission")
        ]


class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="user_roles")
    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        db_table = "accounts_user_role"
        constraints = [models.UniqueConstraint(fields=["user", "role"], name="uq_user_role")]


class LoginHistory(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_history")
    organization = models.ForeignKey(
        "tenancy.Organization", null=True, on_delete=models.SET_NULL, related_name="+"
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, default="")
    success = models.BooleanField()

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "accounts_login_history"
        ordering = ["-created_at"]


class FailedLoginAttempt(models.Model):
    """Keyed by the attempted email, not a resolved user — a nonexistent
    email is itself a signal worth rate-limiting. Not tenant-scoped: the
    organization isn't known until (if) the email resolves to a real user.
    """

    email = models.EmailField(db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_failed_login_attempt"
        indexes = [models.Index(fields=["email", "created_at"])]
