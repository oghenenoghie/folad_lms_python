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
    # Nullable: a User has at most one of these linked one-to-one profiles
    # (apps.students/apps.staff/apps.parents' `user` FK, related_name
    # student_profile/staff_profile/guardian_profile) — this is how a
    # client discovers "which Student/Staff/Guardian am I", the same
    # getattr(user, "..._profile", None) probe apps.dashboards.services.
    # dashboard_service.get_summary already uses to pick a role, exposed
    # here so a client can address that record directly (e.g. a student
    # submitting their own exam answers).
    student_public_id = serializers.SerializerMethodField()
    staff_public_id = serializers.SerializerMethodField()
    guardian_public_id = serializers.SerializerMethodField()

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
            "student_public_id",
            "staff_public_id",
            "guardian_public_id",
        ]

    def get_roles(self, obj: User) -> list[str]:
        return list(obj.user_roles.values_list("role__name", flat=True))

    def get_student_public_id(self, obj: User) -> str | None:
        student = getattr(obj, "student_profile", None)
        return str(student.public_id) if student else None

    def get_staff_public_id(self, obj: User) -> str | None:
        staff = getattr(obj, "staff_profile", None)
        return str(staff.public_id) if staff else None

    def get_guardian_public_id(self, obj: User) -> str | None:
        guardian = getattr(obj, "guardian_profile", None)
        return str(guardian.public_id) if guardian else None
