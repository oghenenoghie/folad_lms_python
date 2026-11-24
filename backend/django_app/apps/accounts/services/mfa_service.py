"""MFA enrollment — thin views, fat services (§11 ARCHITECTURE.md).
Extracted from apps.accounts.views' MFAEnrollView/MFAVerifyView so the
server-rendered security page (apps.web) can drive the identical flow
without re-implementing it — both callers hit this module, not each
other. Behavior (including the pyotp/provisioning_uri format and the
exact save() update_fields) is unchanged from before the extraction.
"""
import pyotp

from .auth_service import verify_totp


class MFANotInProgressError(Exception):
    pass


class MFAInvalidCodeError(Exception):
    pass


def provisioning_uri_for(user) -> str:
    return pyotp.TOTP(user.mfa_secret).provisioning_uri(name=user.email, issuer_name="SMS")


def start_enrollment(user) -> tuple[str, str]:
    """Generates and persists a new TOTP secret, returning (secret,
    otpauth_uri) for the caller to render as a QR code / manual-entry
    string. Overwrites any prior in-progress (unconfirmed) enrollment."""
    secret = pyotp.random_base32()
    user.mfa_secret = secret
    user.save(update_fields=["mfa_secret"])
    return secret, provisioning_uri_for(user)


def confirm_enrollment(*, user, code: str) -> None:
    if not user.mfa_secret:
        raise MFANotInProgressError("no MFA enrollment in progress")
    if not verify_totp(user.mfa_secret, code):
        raise MFAInvalidCodeError("invalid MFA code")
    user.mfa_enabled = True
    user.save(update_fields=["mfa_enabled"])
