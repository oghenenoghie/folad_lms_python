"""DRF authentication: verifies the access JWT, loads the user, and
activates the tenant context (app-layer contextvar + Postgres RLS GUC)
for the rest of the request — see §7 and the auth sequence in §8
ARCHITECTURE.md.
"""
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from apps.tenancy.context import activate_organization

from .jwt import TokenError, decode_token
from .models import User


class JWTAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header:
            return None
        parts = header.split()
        if len(parts) != 2 or parts[0] != self.keyword:
            return None
        token = parts[1]

        try:
            payload = decode_token(token, expected_type="access")
        except TokenError as exc:
            raise AuthenticationFailed(str(exc)) from exc

        try:
            user = User.all_tenants.get(pk=int(payload["sub"]), is_active=True)
        except User.DoesNotExist as exc:
            raise AuthenticationFailed("user not found or inactive") from exc

        # The token's org claim is trusted only because we just verified the
        # signature above; it is never taken from unauthenticated client input.
        activate_organization(user.organization_id)
        return (user, token)

    def authenticate_header(self, request):
        return self.keyword
