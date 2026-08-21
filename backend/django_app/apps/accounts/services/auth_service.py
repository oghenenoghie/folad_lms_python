"""Login business logic — thin views, fat services (§11 ARCHITECTURE.md).
Finding a user by email and recording auth events both happen before a
tenant context exists, so this module deliberately uses `User.all_tenants`
/ `LoginHistory.all_tenants` throughout rather than the tenant-scoped
`objects` manager.
"""
import pyotp
from django.conf import settings
from django.utils import timezone

from apps.accounts.jwt import TokenPair, issue_token_pair
from apps.accounts.models import FailedLoginAttempt, LoginHistory, User
from apps.tenancy.context import activate_organization


class InvalidCredentialsError(Exception):
    pass


class AccountLockedError(Exception):
    pass


class MFARequiredError(Exception):
    pass


class MFAInvalidError(Exception):
    pass


def _record_failed_attempt(email: str, ip_address: str | None) -> None:
    FailedLoginAttempt.objects.create(email=email, ip_address=ip_address)


def _record_login_history(user: User | None, ip_address, user_agent, *, success: bool) -> None:
    if user is None or user.organization_id is None:
        # No tenant-scoped audit trail for platform-level (org=None) accounts —
        # see the RLS note in accounts/migrations/0003_enable_rls.py.
        return
    LoginHistory.all_tenants.create(
        user=user,
        organization=user.organization,
        ip_address=ip_address,
        user_agent=user_agent[:255],
        success=success,
    )


def _is_locked_out(email: str) -> bool:
    window_start = timezone.now() - settings.LOGIN_LOCKOUT_WINDOW
    count = FailedLoginAttempt.objects.filter(email__iexact=email, created_at__gte=window_start).count()
    return count >= settings.LOGIN_LOCKOUT_THRESHOLD


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def login(
    *, email: str, password: str, totp_code: str | None, ip_address: str | None, user_agent: str
) -> TokenPair:
    if _is_locked_out(email):
        raise AccountLockedError("too many failed attempts; try again later")

    try:
        user = User.all_tenants.get(email__iexact=email)
    except User.DoesNotExist as exc:
        _record_failed_attempt(email, ip_address)
        raise InvalidCredentialsError("invalid email or password") from exc

    # The org is now known (the user is identified, even though not yet
    # authenticated) — activate it so the RLS-protected LoginHistory writes
    # below are correctly scoped. See accounts/migrations/0003_enable_rls.py.
    activate_organization(user.organization_id)

    if not user.is_active or not user.check_password(password):
        _record_failed_attempt(email, ip_address)
        _record_login_history(user, ip_address, user_agent, success=False)
        raise InvalidCredentialsError("invalid email or password")

    if user.mfa_enabled:
        if not totp_code:
            raise MFARequiredError("MFA code required")
        if not verify_totp(user.mfa_secret, totp_code):
            _record_failed_attempt(email, ip_address)
            raise MFAInvalidError("invalid MFA code")

    _record_login_history(user, ip_address, user_agent, success=True)
    return issue_token_pair(user.id, user.organization_id)
