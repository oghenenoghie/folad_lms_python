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
            cursor.execute(
                f"""
                CREATE POLICY tenant_isolation ON {table_name}
                USING ({org_column} = current_setting('app.current_org', true)::bigint)
                """
            )

    def backwards(apps, schema_editor):
        if schema_editor.connection.vendor != "postgresql":
            return
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name}")
            cursor.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")

    return migrations.RunPython(forwards, backwards)
