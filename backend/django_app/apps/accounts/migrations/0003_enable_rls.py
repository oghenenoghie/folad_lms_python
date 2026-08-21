from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_initial"),
    ]

    # accounts_user deliberately does NOT get RLS: resolving a user by email
    # at login is an inherently cross-tenant, pre-authentication lookup (we
    # don't know the org until we've found the user) — an audited
    # platform-level code path, same carve-out §7 ARCHITECTURE.md grants
    # SUPER_ADMIN reporting. accounts_login_history is written only after
    # the org is known (auth_service activates it as soon as the user is
    # resolved, before any password check), so RLS applies cleanly there.
    operations = [
        enable_rls("accounts_login_history"),
    ]
