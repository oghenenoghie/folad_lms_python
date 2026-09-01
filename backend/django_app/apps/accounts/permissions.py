"""Centralized, data-driven RBAC (§8 ARCHITECTURE.md). No permission string
is hard-coded in a view's logic beyond the single `require_permission(code)`
call — the code resolves against the DB (Role -> RolePermission -> Permission),
cached per-(user, organization) in Redis and invalidated by accounts.signals
on any grant change.
"""
from rest_framework.permissions import BasePermission

from .cache_keys import permission_cache_key
from .models import Permission

PERMISSION_CACHE_TTL = 300


def get_user_permission_codes(user) -> set[str]:
    from django.core.cache import cache

    org_id = user.organization_id
    key = permission_cache_key(user.id, org_id)
    cached = cache.get(key)
    if cached is not None:
        return set(cached)

    codes = set(
        Permission.objects.filter(roles__user_roles__user_id=user.id)
        .values_list("code", flat=True)
        .distinct()
    )
    cache.set(key, list(codes), timeout=PERMISSION_CACHE_TTL)
    return codes


class HasPermission(BasePermission):
    code: str = ""

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if user.is_superuser:
            return True
        return self.code in get_user_permission_codes(user)


def require_permission(code: str) -> type[HasPermission]:
    """Returns a DRF permission class bound to `code`, e.g.
    `permission_classes = [require_permission("students.view")]`.
    """
    return type(f"RequirePermission_{code.replace('.', '_')}", (HasPermission,), {"code": code})


class IsSuperUser(BasePermission):
    """Gate for the Users & Roles admin API (apps.accounts.admin_views) —
    deliberately *not* `require_permission(...)`. That system grants
    permissions through Role/RolePermission, which this API itself edits;
    gating role/permission management on a permission a role could grant
    itself would let any org admin escalate their own access. Same
    is_superuser-only boundary User.has_perm() already documents for
    Django Admin (see apps.accounts.models.User) — this just gives
    superusers a JSON API/frontend option instead of only Django Admin.
    """

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and getattr(user, "is_authenticated", False) and user.is_superuser)
