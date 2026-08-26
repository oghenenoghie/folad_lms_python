"""Migration helper for enabling RLS on a tenant-owned table (§7
ARCHITECTURE.md, layer 3 of the defence-in-depth stack). Postgres-only —
a no-op under SQLite so `migrate` still works there for local desktop
dev without RLS enforcement (the app-layer TenantManager still applies).
"""
from django.db import migrations


def enable_rls(table_name: str, org_column: str = "organization_id"):
    """Return a RunPython pair (forwards, backwards) enabling/disabling RLS
    with a tenant-isolation policy on `table_name`, keyed on `org_column`.
    """

    def forwards(apps, schema_editor):
        if schema_editor.connection.vendor != "postgresql":
            return
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
            cursor.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
            # current_setting(..., true) can return '' rather than NULL for an
            # unset custom GUC on some connections (observed under
            # pytest-django's per-test transaction rollback, which reverts a
            # session-level set_config()). ''::bigint raises a hard DataError
            # instead of failing closed, so NULLIF coerces it to NULL first —
            # NULL never equals org_column, so the query still returns zero
            # rows rather than crashing.
            cursor.execute(
                f"""
                CREATE POLICY tenant_isolation ON {table_name}
                USING ({org_column} = NULLIF(current_setting('app.current_org', true), '')::bigint)
                """
            )

    def backwards(apps, schema_editor):
        if schema_editor.connection.vendor != "postgresql":
            return
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name}")
            cursor.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")

    return migrations.RunPython(forwards, backwards)


def make_append_only(table_name: str):
    """Return a RunPython pair (forwards, backwards) that forbids UPDATE and
    DELETE on `table_name` at the database level (§15 ARCHITECTURE.md:
    "Immutable audit + append-only ledger by DB trigger"). Postgres-only,
    same convention as `enable_rls` — a no-op under SQLite.

    `reject_mutation()` is a single shared trigger function (PL/pgSQL
    functions aren't table-specific; `TG_TABLE_NAME`/`TG_OP` are populated
    per-invocation from trigger context), created idempotently so calling
    this for multiple tables across separate migrations never conflicts.
    Intended for genuinely immutable historical rows (an audit trail, a
    ledger) — never for a soft-deletable model, since even setting
    `deleted_at` would be rejected.
    """

    def forwards(apps, schema_editor):
        if schema_editor.connection.vendor != "postgresql":
            return
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE OR REPLACE FUNCTION reject_mutation() RETURNS trigger AS $$
                BEGIN
                    RAISE EXCEPTION '% is append-only: % not permitted', TG_TABLE_NAME, TG_OP;
                END;
                $$ LANGUAGE plpgsql
                """
            )
            cursor.execute(
                f"""
                CREATE TRIGGER {table_name}_append_only
                BEFORE UPDATE OR DELETE ON {table_name}
                FOR EACH ROW EXECUTE FUNCTION reject_mutation()
                """
            )

    def backwards(apps, schema_editor):
        if schema_editor.connection.vendor != "postgresql":
            return
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(f"DROP TRIGGER IF EXISTS {table_name}_append_only ON {table_name}")

    return migrations.RunPython(forwards, backwards)


def add_platform_mode_bypass(table_name: str, org_column: str = "organization_id"):
    """Extend an existing `tenant_isolation` policy (see `enable_rls`
    above) with an OR clause keyed on the `app.platform_mode` session GUC
    — the audited escape hatch Django Admin uses to see across every
    organization at once (a cross-tenant ops console, not a request
    scoped to one tenant), set only by
    apps.tenancy.middleware.AdminPlatformModeMiddleware for staff-
    authenticated `/admin/` requests. Never touched by the JWT API or the
    `/app/` server-rendered UI, so this cannot widen what either of those
    can see.
    """

    def forwards(apps, schema_editor):
        if schema_editor.connection.vendor != "postgresql":
            return
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                f"""
                ALTER POLICY tenant_isolation ON {table_name}
                USING (
                    {org_column} = NULLIF(current_setting('app.current_org', true), '')::bigint
                    OR current_setting('app.platform_mode', true) = 'true'
                )
                """
            )

    def backwards(apps, schema_editor):
        if schema_editor.connection.vendor != "postgresql":
            return
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                f"""
                ALTER POLICY tenant_isolation ON {table_name}
                USING ({org_column} = NULLIF(current_setting('app.current_org', true), '')::bigint)
                """
            )

    return migrations.RunPython(forwards, backwards)
