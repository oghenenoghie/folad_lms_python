"""Views for the Users & Roles admin API — thin views, fat services (§11
ARCHITECTURE.md). Every view here is gated by IsSuperUser, never
require_permission(): see apps.accounts.permissions.IsSuperUser for why.

Unlike every other TenantListCreateAPIView/TenantRetrieveUpdateDestroyAPIView
in this codebase, these deliberately read across every organization — the
same platform-ops, cross-tenant visibility Django Admin's TenantAdminMixin
already gives staff over User/Role (apps.core.admin), because this API is
just a JSON/frontend alternative to that same console, gated the same way.
"""
from rest_framework.permissions import IsAuthenticated

from apps.core.generics import TenantListAPIView, TenantListCreateAPIView, TenantRetrieveUpdateDestroyAPIView
from apps.core.responses import error_envelope

from .admin_serializers import PermissionAdminSerializer, RoleAdminSerializer, UserAdminSerializer
from .models import Permission, Role, User
from .permissions import IsSuperUser
from .services import role_admin_service, user_admin_service
from .services.role_admin_service import RoleIsSystemError


class UserAdminListCreateView(TenantListCreateAPIView):
    serializer_class = UserAdminSerializer
    permission_classes = [IsAuthenticated, IsSuperUser]

    def get_queryset(self):
        qs = User.all_tenants.filter(deleted_at__isnull=True)
        organization_id = self.request.query_params.get("organization_id")
        if organization_id:
            qs = qs.filter(organization__public_id=organization_id)
        return qs.order_by("email")

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        roles = data.pop("roles", None)
        password = data.pop("password", None)
        serializer.instance = user_admin_service.create_user(
            actor=self.request.user, roles=roles, password=password, **data
        )


class UserAdminDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = UserAdminSerializer
    permission_classes = [IsAuthenticated, IsSuperUser]

    def get_queryset(self):
        return User.all_tenants.filter(deleted_at__isnull=True)

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        roles = data.pop("roles", None)
        password = data.pop("password", None)
        user_admin_service.update_user(
            user=serializer.instance, actor=self.request.user, roles=roles, password=password, **data
        )

    def perform_destroy(self, instance):
        user_admin_service.delete_user(user=instance, actor=self.request.user)


class RoleListCreateView(TenantListCreateAPIView):
    serializer_class = RoleAdminSerializer
    permission_classes = [IsAuthenticated, IsSuperUser]

    def get_queryset(self):
        return Role.objects.order_by("name")

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        permissions = data.pop("permissions", None)
        serializer.instance = role_admin_service.create_role(
            actor=self.request.user, permissions=permissions, **data
        )


class RoleDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = RoleAdminSerializer
    permission_classes = [IsAuthenticated, IsSuperUser]

    def get_queryset(self):
        return Role.objects.all()

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except RoleIsSystemError as exc:
            return error_envelope(str(exc), status=403)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except RoleIsSystemError as exc:
            return error_envelope(str(exc), status=403)

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        permissions = data.pop("permissions", None)
        role_admin_service.update_role(
            role=serializer.instance, actor=self.request.user, permissions=permissions, **data
        )

    def perform_destroy(self, instance):
        role_admin_service.delete_role(role=instance, actor=self.request.user)


class PermissionListView(TenantListAPIView):
    """Read-only reference catalog — permissions are seeded, not created
    through the API (see admin_serializers.py). Unpaginated: the whole
    catalog (~250 rows) is exactly what a Role permission-picker UI needs
    in one shot, not spread across pages."""

    serializer_class = PermissionAdminSerializer
    permission_classes = [IsAuthenticated, IsSuperUser]
    pagination_class = None

    def get_queryset(self):
        return Permission.objects.all()
