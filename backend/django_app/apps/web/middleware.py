"""Bridges Django session auth to the RLS tenant context (UI_MIGRATION_PLAN.md
§5). Every existing authenticated code path activates the tenant context
itself — `JWTAuthentication.authenticate()` for the JSON API, `auth_service`
during login — but nothing does that for a plain Django session, which is
what every view under apps.web (the server-rendered UI, mounted at `/app/`)
runs under. Without this, `TenantManager`-scoped querysets in a `/app/` view
would silently return nothing, exactly like the pre-existing Django Admin
RLS gap this project already documents.

Scoped strictly to the `/app/` prefix — never touches `/api/`, `/admin/`,
or `/health/` — so this cannot change JWT-authenticated request behavior.
"""
from apps.tenancy.context import activate_organization


class WebTenantContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/app/") and request.user.is_authenticated:
            activate_organization(request.user.organization_id)
        return self.get_response(request)
