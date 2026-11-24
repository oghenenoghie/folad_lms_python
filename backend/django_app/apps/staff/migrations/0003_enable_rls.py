from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("staff", "0002_seed_permissions"),
    ]

    operations = [
        enable_rls("staff_staff"),
        enable_rls("staff_teacher"),
    ]
