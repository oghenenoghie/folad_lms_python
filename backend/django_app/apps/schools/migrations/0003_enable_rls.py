from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("schools", "0002_seed_permissions"),
    ]

    operations = [
        enable_rls("schools_school"),
        enable_rls("schools_campus"),
        enable_rls("schools_academic_year"),
        enable_rls("schools_term"),
        enable_rls("schools_department"),
    ]
