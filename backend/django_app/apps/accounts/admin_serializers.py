"""Serializers for the Users & Roles admin API (apps.accounts.admin_views) —
gated by IsSuperUser, not require_permission(); see permissions.py. Mirrors
what Django Admin's UserAdmin/RoleAdmin/PermissionAdmin already expose
(§11 ARCHITECTURE.md), as a JSON/frontend alternative for superusers.
"""
from rest_framework import serializers

from apps.core.serializers import PublicIdRelatedField
from apps.tenancy.models import Organization

from .models import Permission, Role, User


class PermissionAdminSerializer(serializers.ModelSerializer):
    """Read-only reference catalog — Permission rows are seeded, never
    created/edited through the API (see apps.accounts.permissions docstring)."""

    class Meta:
        model = Permission
        fields = ["code", "module", "action", "description"]
        read_only_fields = fields


class RoleAdminSerializer(serializers.ModelSerializer):
    # A real ManyToManyField (Role.permissions, through RolePermission with
    # no extra columns), so SlugRelatedField's normal read/write M2M
    # handling applies directly — same as RoleAdmin.save_model's
    # obj.permissions.set(...) in Django Admin.
    permissions = serializers.SlugRelatedField(
        slug_field="code", many=True, queryset=Permission.objects.all(), required=False
    )
    organization = PublicIdRelatedField(
        queryset=Organization.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Role
        fields = ["public_id", "name", "label", "is_system", "organization", "permissions"]
        read_only_fields = ["public_id", "is_system"]


class UserAdminSerializer(serializers.ModelSerializer):
    organization = PublicIdRelatedField(
        queryset=Organization.objects.all(), required=False, allow_null=True
    )
    # `roles` isn't a real attribute on User (the User<->Role relationship
    # only exists via the UserRole join table, with no declared M2M
    # accessor on User) — accept/emit it as a plain list of role names and
    # resolve/serialize by hand below, rather than forcing a SlugRelatedField
    # onto an attribute that doesn't exist.
    roles = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True, trim_whitespace=False)
    # Set only on the in-memory instance user_admin_service.create_user()
    # returns right after generating a password — never persisted, never
    # present on a user re-fetched from the DB. Same convention as
    # apps.students.serializers.StudentSerializer.generated_password.
    generated_password = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "public_id",
            "email",
            "first_name",
            "last_name",
            "organization",
            "is_active",
            "is_staff",
            "is_superuser",
            "roles",
            "password",
            "generated_password",
        ]
        read_only_fields = ["public_id"]

    def get_generated_password(self, obj):
        return getattr(obj, "_generated_password", None)

    def validate_roles(self, value: list[str]) -> list[Role]:
        roles = list(Role.objects.filter(name__in=value))
        missing = set(value) - {role.name for role in roles}
        if missing:
            raise serializers.ValidationError(f"unknown role name(s): {', '.join(sorted(missing))}")
        return roles

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["roles"] = list(instance.user_roles.values_list("role__name", flat=True))
        return data
