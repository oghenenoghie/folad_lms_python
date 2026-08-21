"""Resets the app-layer contextvar at the start of every request — cheap,
no DB access, so dependency-free endpoints like /health stay dependency-free.
The Postgres RLS GUC is a connection-scoped setting, not a per-request one:
apps/tenancy/apps.py resets it once whenever a new physical connection is
opened (see the connection_created handler there), and every code path that
actually touches an RLS-protected table calls activate_organization() with
a real value first (JWTAuthentication on every authenticated request; the
login flow as soon as it resolves a user). No currently-anonymous code path
touches an RLS-protected table without one of those running first.
"""
from .context import set_current_organization_id


class TenancyResetMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_organization_id(None)
        return self.get_response(request)
