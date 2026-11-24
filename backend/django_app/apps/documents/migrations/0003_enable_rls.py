from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0002_seed_permissions"),
    ]

    operations = [
        enable_rls("documents_document"),
    ]
