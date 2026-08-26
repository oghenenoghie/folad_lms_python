from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0004_alter_guardianstudent_options"),
    ]

    operations = [
        add_platform_mode_bypass("students_student"),
        add_platform_mode_bypass("students_guardian_student"),
    ]
