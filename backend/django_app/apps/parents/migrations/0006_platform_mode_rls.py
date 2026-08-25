from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [
        ("parents", "0005_alter_guardianstudent_options"),
    ]

    operations = [
        add_platform_mode_bypass("parents_guardian"),
        add_platform_mode_bypass("parents_guardian_student"),
    ]
