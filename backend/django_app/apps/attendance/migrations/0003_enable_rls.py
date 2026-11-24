from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0002_seed_permissions"),
    ]

    operations = [
        enable_rls("attendance_attendance"),
        enable_rls("attendance_attendance_audit"),
    ]
