"""Redis-cached permission set for (user, organization) — invalidated by
signals.py on any role/permission grant change (§8 ARCHITECTURE.md)."""
from django.core.cache import cache

PERMISSION_CACHE_TTL = 300  # seconds


def permission_cache_key(user_id: int, organization_id: int | None) -> str:
    return f"perms:{user_id}:{organization_id}"


def invalidate_user_permissions(user_id: int, organization_id: int | None) -> None:
    cache.delete(permission_cache_key(user_id, organization_id))
