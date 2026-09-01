from django.urls import path

from .admin_views import (
    PermissionListView,
    RoleDetailView,
    RoleListCreateView,
    UserAdminDetailView,
    UserAdminListCreateView,
)
from .views import LoginView, LogoutView, MeView, MFAEnrollView, MFAVerifyView, RefreshView

urlpatterns = [
    path("auth/login", LoginView.as_view(), name="auth-login"),
    path("auth/refresh", RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout", LogoutView.as_view(), name="auth-logout"),
    path("auth/mfa/enroll", MFAEnrollView.as_view(), name="auth-mfa-enroll"),
    path("auth/mfa/verify", MFAVerifyView.as_view(), name="auth-mfa-verify"),
    path("auth/me", MeView.as_view(), name="auth-me"),
    # Users & Roles admin API — superuser-gated, not RBAC-gated (see
    # apps.accounts.permissions.IsSuperUser).
    path("admin/users", UserAdminListCreateView.as_view(), name="admin-user-list-create"),
    path("admin/users/<uuid:public_id>", UserAdminDetailView.as_view(), name="admin-user-detail"),
    path("admin/roles", RoleListCreateView.as_view(), name="admin-role-list-create"),
    path("admin/roles/<uuid:public_id>", RoleDetailView.as_view(), name="admin-role-detail"),
    path("admin/permissions", PermissionListView.as_view(), name="admin-permission-list"),
]
