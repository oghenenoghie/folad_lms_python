import pyotp
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.core.responses import envelope, error_envelope

from . import jwt as jwt_lib
from .serializers import LoginSerializer, MFAVerifySerializer, RefreshSerializer, UserSerializer
from .services import auth_service


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _token_pair_data(pair: jwt_lib.TokenPair) -> dict:
    return {
        "access": pair.access,
        "refresh": pair.refresh,
        "access_expires_in": pair.access_expires_in,
        "refresh_expires_in": pair.refresh_expires_in,
    }


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            pair = auth_service.login(
                email=data["email"],
                password=data["password"],
                totp_code=data.get("totp_code") or None,
                ip_address=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except auth_service.AccountLockedError as exc:
            return error_envelope(str(exc), status=423)
        except auth_service.MFARequiredError as exc:
            return error_envelope(str(exc), errors=["mfa_required"], status=401)
        except auth_service.MFAInvalidError as exc:
            return error_envelope(str(exc), errors=["mfa_invalid"], status=401)
        except auth_service.InvalidCredentialsError as exc:
            return error_envelope(str(exc), status=401)

        return envelope(_token_pair_data(pair), message="login successful")


class RefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            pair = jwt_lib.rotate_refresh_token(serializer.validated_data["refresh"])
        except jwt_lib.TokenReuseDetected as exc:
            return error_envelope(str(exc), status=401)
        except jwt_lib.TokenError as exc:
            return error_envelope(str(exc), status=401)

        return envelope(_token_pair_data(pair), message="token refreshed")


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh")
        if refresh:
            jwt_lib.revoke_refresh_token(refresh)
        return envelope(message="logged out")


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return envelope(UserSerializer(request.user).data)


class MFAEnrollView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        secret = pyotp.random_base32()
        user.mfa_secret = secret
        user.save(update_fields=["mfa_secret"])
        uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="SMS")
        return envelope({"secret": secret, "otpauth_uri": uri}, message="scan with an authenticator app, then verify")


class MFAVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = MFAVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user

        if not user.mfa_secret:
            return error_envelope("no MFA enrollment in progress", status=400)
        if not auth_service.verify_totp(user.mfa_secret, serializer.validated_data["code"]):
            return error_envelope("invalid MFA code", status=401)

        user.mfa_enabled = True
        user.save(update_fields=["mfa_enabled"])
        return envelope(message="MFA enabled")
