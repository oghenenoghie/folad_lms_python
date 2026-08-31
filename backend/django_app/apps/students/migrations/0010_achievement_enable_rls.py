from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0009_achievement"),
    ]

    operations = [
        enable_rls("students_achievement"),
    ]
