from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0003_enable_rls"),
    ]

    operations = [
        add_platform_mode_bypass("attendance_attendance"),
        add_platform_mode_bypass("attendance_attendance_audit"),
    ]
