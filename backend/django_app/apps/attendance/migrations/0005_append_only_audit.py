from django.db import migrations

from apps.tenancy.db import make_append_only


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0004_platform_mode_rls"),
    ]

    operations = [
        make_append_only("attendance_attendance_audit"),
    ]
