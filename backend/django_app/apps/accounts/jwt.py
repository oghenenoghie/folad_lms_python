"""JWT issuance + rotating refresh tokens with family reuse detection
(§8, §13 ARCHITECTURE.md). Refresh records live in Redis (via Django's
cache) for instant revocation — never in Postgres.

Reuse-detection design: each refresh token carries a `family` id shared
across every token descended from one login. Redis holds one tombstone
record per jti (`revoked` flag, kept until natural expiry) plus a pointer
to the family's current active jti. Presenting an already-rotated jti
means the token was stolen and replayed — the whole family is revoked.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
from django.conf import settings
from django.core.cache import cache

ALGORITHM = "HS256"


class TokenError(Exception):
    """Base for all token validation failures — callers should treat as 401."""


class TokenReuseDetected(TokenError):
    """A refresh token that was already rotated was presented again."""


def _secret() -> str:
    return getattr(settings, "JWT_SECRET_KEY", None) or settings.SECRET_KEY


def _jti_key(jti: str) -> str:
    return f"refresh:jti:{jti}"


def _family_active_key(family_id: str) -> str:
    return f"refresh:family:{family_id}:active_jti"


@dataclass(frozen=True, slots=True)
class TokenPair:
    access: str
    refresh: str
    access_expires_in: int
    refresh_expires_in: int


def _encode_access_token(user_id: int, organization_id: int | None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "org": organization_id,
        "jti": str(uuid.uuid4()),
        "type": "access",
        "iat": now,
        "exp": now + settings.JWT_ACCESS_TOKEN_TTL,
    }
    return pyjwt.encode(payload, _secret(), algorithm=ALGORITHM)


def _encode_refresh_token(user_id: int, jti: str, family_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "family": family_id,
        "type": "refresh",
        "iat": now,
        "exp": now + settings.JWT_REFRESH_TOKEN_TTL,
    }
    return pyjwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_token(token: str, expected_type: str) -> dict:
    try:
        payload = pyjwt.decode(token, _secret(), algorithms=[ALGORITHM])
    except pyjwt.ExpiredSignatureError as exc:
        raise TokenError("token expired") from exc
    except pyjwt.InvalidTokenError as exc:
        raise TokenError("invalid token") from exc
    if payload.get("type") != expected_type:
        raise TokenError(f"expected a {expected_type} token")
    return payload


def _refresh_ttl_seconds() -> int:
    return int(settings.JWT_REFRESH_TOKEN_TTL.total_seconds())


def issue_token_pair(user_id: int, organization_id: int | None) -> TokenPair:
    """Start a new refresh-token family (login)."""
    family_id = str(uuid.uuid4())
    jti = str(uuid.uuid4())
    ttl = _refresh_ttl_seconds()
    cache.set(_jti_key(jti), {"family": family_id, "user_id": user_id, "revoked": False}, timeout=ttl)
    cache.set(_family_active_key(family_id), jti, timeout=ttl)
    return TokenPair(
        access=_encode_access_token(user_id, organization_id),
        refresh=_encode_refresh_token(user_id, jti, family_id),
        access_expires_in=int(settings.JWT_ACCESS_TOKEN_TTL.total_seconds()),
        refresh_expires_in=ttl,
    )


def rotate_refresh_token(refresh_token: str) -> TokenPair:
    """Validate, rotate, and reissue. Raises TokenReuseDetected (family
    revoked as a side effect) or TokenError on any other invalid input.
    Re-reads the user's current organization from the database rather than
    trusting a claim carried on the old token, so a mid-session tenant
    reassignment takes effect on the very next refresh."""
    payload = decode_token(refresh_token, expected_type="refresh")
    jti = payload["jti"]
    user_id = int(payload["sub"])

    record = cache.get(_jti_key(jti))
    if record is None:
        raise TokenError("unknown or expired refresh token")

    if record["revoked"]:
        _revoke_family(record["family"])
        raise TokenReuseDetected("refresh token reuse detected; session revoked")

    from .models import User

    try:
        user = User.all_tenants.get(pk=user_id, is_active=True)
    except User.DoesNotExist as exc:
        raise TokenError("user not found or inactive") from exc

    record["revoked"] = True
    cache.set(_jti_key(jti), record, timeout=_refresh_ttl_seconds())

    family_id = record["family"]
    new_jti = str(uuid.uuid4())
    ttl = _refresh_ttl_seconds()
    cache.set(
        _jti_key(new_jti), {"family": family_id, "user_id": user_id, "revoked": False}, timeout=ttl
    )
    cache.set(_family_active_key(family_id), new_jti, timeout=ttl)

    return TokenPair(
        access=_encode_access_token(user_id, user.organization_id),
        refresh=_encode_refresh_token(user_id, new_jti, family_id),
        access_expires_in=int(settings.JWT_ACCESS_TOKEN_TTL.total_seconds()),
        refresh_expires_in=ttl,
    )


def _revoke_family(family_id: str) -> None:
    active_jti = cache.get(_family_active_key(family_id))
    if active_jti:
        record = cache.get(_jti_key(active_jti))
        if record:
            record["revoked"] = True
            cache.set(_jti_key(active_jti), record, timeout=_refresh_ttl_seconds())
    cache.delete(_family_active_key(family_id))


def revoke_refresh_token(refresh_token: str) -> None:
    """Logout: revoke the presented token's whole family."""
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except TokenError:
        return
    _revoke_family(payload["family"])
