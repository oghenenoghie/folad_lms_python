from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("assignments", "0002_seed_permissions"),
    ]

    operations = [
        enable_rls("assignments_assignment"),
        enable_rls("assignments_submission"),
    ]
