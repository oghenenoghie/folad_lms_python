from rest_framework import serializers

from .models import User


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    totp_code = serializers.CharField(required=False, allow_blank=True, default="")


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class MFAVerifySerializer(serializers.Serializer):
    code = serializers.CharField()


class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "public_id",
            "email",
            "first_name",
            "last_name",
            "organization_id",
            "mfa_enabled",
            "roles",
        ]

    def get_roles(self, obj: User) -> list[str]:
        return list(obj.user_roles.values_list("role__name", flat=True))
