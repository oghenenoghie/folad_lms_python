from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [
        ("staff", "0004_alter_teacher_options"),
    ]

    operations = [
        add_platform_mode_bypass("staff_staff"),
        add_platform_mode_bypass("staff_teacher"),
    ]
