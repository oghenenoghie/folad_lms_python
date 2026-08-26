"""Request-scoped tenant context.

The current organization is resolved once per request, strictly from
`request.user.organization_id` (never from client input — see
TenancyMiddleware), and stashed here for the duration of the request.
`TenantManager` reads it to scope every query.
"""
import contextvars

_current_org_id: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "current_org_id", default=None
)


def set_current_organization_id(org_id: int | None) -> None:
    _current_org_id.set(org_id)


def get_current_organization_id() -> int | None:
    return _current_org_id.get()


class TenantContextError(RuntimeError):
    """Raised when tenant-scoped code runs with no organization in context."""


def activate_organization(org_id: int | None) -> None:
    """Set the app-layer contextvar and, on Postgres, the `app.current_org`
    session GUC that RLS policies key on (§7 ARCHITECTURE.md). Called once
    per request by JWTAuthentication on successful auth — never from
    client-supplied input.

    Always writes the GUC, even for org_id=None (platform-level accounts):
    connections are reused across requests (CONN_MAX_AGE / pooling), so
    skipping the write here would let a previous request's org id linger
    on the connection and leak through RLS to an unrelated request. `0`
    is used as the "no organization" sentinel — organization ids are a
    bigserial starting at 1, so it can never collide with a real tenant.

    Also clears `app.platform_mode` (see `activate_platform_mode`) in the
    same round trip, for the same reuse reason: a connection that just
    served an admin request must not leak platform-mode visibility into
    the next request that reuses it.
    """
    set_current_organization_id(org_id)
    from django.db import connection

    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        # SET does not accept bind parameters over the wire protocol; set_config() does.
        # is_local=false: persists for the session (connection), not just the transaction.
        cursor.execute(
            "SELECT set_config('app.current_org', %s, false), set_config('app.platform_mode', 'false', false)",
            [str(org_id) if org_id is not None else "0"],
        )


def activate_platform_mode() -> None:
    """Set the `app.platform_mode` session GUC that every tenant_isolation
    RLS policy ORs against (see apps.tenancy.db.add_platform_mode_bypass)
    — the audited, narrowly-scoped escape hatch that lets Django Admin (a
    cross-tenant ops console per apps.core.admin.TenantAdminMixin) see
    every organization in one request, instead of the single org
    `activate_organization` scopes normal requests to.

    Called only by apps.tenancy.middleware.AdminPlatformModeMiddleware,
    for staff-authenticated `/admin/` requests — never from client-
    supplied input, and never reachable from the JWT API or `/app/` UI.
    """
    from django.db import connection

    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.platform_mode', 'true', false)")
