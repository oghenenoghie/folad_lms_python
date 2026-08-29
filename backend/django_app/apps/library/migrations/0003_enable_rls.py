from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("library", "0002_seed_permissions"),
    ]

    operations = [
        enable_rls("library_book"),
        enable_rls("library_copy"),
        enable_rls("library_member"),
        enable_rls("library_loan"),
        enable_rls("library_fine"),
    ]
