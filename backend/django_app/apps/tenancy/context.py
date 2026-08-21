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
    """
    set_current_organization_id(org_id)
    from django.db import connection

    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        # SET does not accept bind parameters over the wire protocol; set_config() does.
        # is_local=false: persists for the session (connection), not just the transaction.
        cursor.execute(
            "SELECT set_config('app.current_org', %s, false)",
            [str(org_id) if org_id is not None else "0"],
        )
