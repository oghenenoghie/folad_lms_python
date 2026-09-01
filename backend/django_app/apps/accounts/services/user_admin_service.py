"""Thin views, fat services (§11 ARCHITECTURE.md). Backs the superuser-gated
Users admin API (apps.accounts.admin_views) — deliberately separate from
apps.accounts.services.auth_service (login/token concerns), mirroring the
apps.students.services.student_service split between provisioning and auth.
"""
import secrets
import string

from django.utils import timezone

from apps.accounts.models import Role, User, UserRole

_PASSWORD_ALPHABET = string.ascii_letters + string.digits
_PASSWORD_LENGTH = 12


def _generate_password() -> str:
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(_PASSWORD_LENGTH))


def _sync_roles(*, user: User, roles: list[Role], actor: User) -> None:
    current_role_ids = set(user.user_roles.values_list("role_id", flat=True))
    target_role_ids = {role.id for role in roles}

    UserRole.objects.filter(user=user, role_id__in=current_role_ids - target_role_ids).delete()
    for role in roles:
        if role.id not in current_role_ids:
            UserRole.objects.create(user=user, role=role, granted_by=actor)


def create_user(
    *, actor, roles: list[Role] | None = None, password: str | None = None, organization=None, **fields
) -> User:
    """Returns the created user; when no password was supplied, the
    one-time plaintext is stashed on `_generated_password` (never
    persisted) for the serializer to surface exactly once, same as
    apps.students.services.student_service.provision_login.

    An omitted `organization` defaults to the acting superuser's own —
    the frontend has no cross-tenant organization picker (this codebase
    never exposes raw organization PKs, only public_ids, and no endpoint
    hands those out), so leaving it unset here would otherwise silently
    create an orgless, platform-level account instead of one scoped to
    whichever school the superuser is actually administering.
    """
    if organization is None:
        organization = actor.organization

    generated_password = None
    if not password:
        generated_password = _generate_password()
        password = generated_password

    user = User.objects.create_user(organization=organization, password=password, **fields)
    if roles:
        _sync_roles(user=user, roles=roles, actor=actor)
    if generated_password:
        user._generated_password = generated_password
    return user


def update_user(*, user: User, actor, roles: list[Role] | None = None, password: str | None = None, **fields) -> User:
    for field, value in fields.items():
        setattr(user, field, value)
    update_fields = [*fields.keys(), "updated_by", "updated_at"]
    user.updated_by = actor
    if password:
        user.set_password(password)
        update_fields.append("password")
    user.save(update_fields=update_fields)

    if roles is not None:
        _sync_roles(user=user, roles=roles, actor=actor)
    return user


def delete_user(*, user: User, actor) -> None:
    user.deleted_at = timezone.now()
    user.updated_by = actor
    user.save(update_fields=["deleted_at", "updated_by", "updated_at"])
