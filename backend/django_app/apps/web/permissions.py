from apps.accounts.permissions import get_user_permission_codes


def can(user, code: str) -> bool:
    """Same rule apps.accounts.permissions.HasPermission enforces on the
    JSON API (superuser bypass, else a real granted permission code) —
    reused here, not reimplemented, so a server-rendered page can never
    show or allow an action the API itself would reject."""
    return bool(user.is_superuser or code in get_user_permission_codes(user))
