from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("parents", "0002_seed_permissions"),
    ]

    operations = [
        enable_rls("parents_guardian"),
    ]
