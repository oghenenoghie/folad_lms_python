"""Resets the app-layer contextvar at the start of every request — cheap,
no DB access, so dependency-free endpoints like /health stay dependency-free.
The Postgres RLS GUC is a connection-scoped setting, not a per-request one:
apps/tenancy/apps.py resets it once whenever a new physical connection is
opened (see the connection_created handler there), and every code path that
actually touches an RLS-protected table calls activate_organization() or
activate_platform_mode() with a real value first (JWTAuthentication on every
authenticated request; the login flow as soon as it resolves a user; this
module's AdminPlatformModeMiddleware for /admin/). No currently-anonymous
code path touches an RLS-protected table without one of those running first.
"""
from .context import activate_platform_mode, set_current_organization_id


class TenancyResetMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_organization_id(None)
        return self.get_response(request)


class AdminPlatformModeMiddleware:
    """Bridges Django Admin's session auth to RLS's platform-mode escape
    hatch (apps.tenancy.db.add_platform_mode_bypass) — mirrors
    apps.web.middleware.WebTenantContextMiddleware, but Admin is a
    cross-tenant ops console (apps.core.admin.TenantAdminMixin already
    uses the unscoped `all_tenants` manager at the app layer for exactly
    this reason), so it activates platform mode rather than scoping to
    the signed-in staff member's own organization.

    Scoped strictly to `/admin/` — never touches `/api/`, `/app/`, or
    `/health/` — so this cannot widen what either of those can see. Must
    run after AuthenticationMiddleware (needs request.user resolved).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/admin/") and request.user.is_authenticated and request.user.is_staff:
            activate_platform_mode()
        return self.get_response(request)
