from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("parents", "0003_seed_permissions"),
    ]

    operations = [
        enable_rls("parents_guardian"),
        enable_rls("parents_guardian_student"),
    ]
