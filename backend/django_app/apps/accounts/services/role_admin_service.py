"""Thin views, fat services (§11 ARCHITECTURE.md). Backs the superuser-gated
Roles admin API (apps.accounts.admin_views).
"""
from apps.accounts.models import Permission, Role


class RoleIsSystemError(Exception):
    """Raised when the API tries to edit or delete a seeded is_system role.
    System roles ship with the platform (migrations/fixtures) — editing or
    deleting one here would silently change what every school using it can
    do; Django Admin allows it deliberately for platform ops, but this
    lower-friction JSON API doesn't. Custom, non-system roles are exactly
    the CUSTOM_ROLE composition this API exists for (§8 ARCHITECTURE.md)."""


def create_role(*, actor, permissions: list[Permission] | None = None, organization=None, **fields) -> Role:
    # Every role created through this API is a custom role by definition —
    # Role.is_system defaults to True (the shape seeded system roles use),
    # so it must be forced off here rather than left to that model default.
    # An omitted `organization` defaults to the acting superuser's own,
    # same reasoning as user_admin_service.create_user.
    if organization is None:
        organization = actor.organization
    role = Role.objects.create(is_system=False, organization=organization, **fields)
    if permissions:
        role.permissions.set(permissions)
    return role


def update_role(*, role: Role, actor, permissions: list[Permission] | None = None, **fields) -> Role:
    if role.is_system:
        raise RoleIsSystemError(f'"{role.name}" is a system role and cannot be edited')
    for field, value in fields.items():
        setattr(role, field, value)
    if fields:
        role.save(update_fields=list(fields.keys()))
    if permissions is not None:
        role.permissions.set(permissions)
    return role


def delete_role(*, role: Role, actor) -> None:
    if role.is_system:
        raise RoleIsSystemError(f'"{role.name}" is a system role and cannot be deleted')
    role.delete()
