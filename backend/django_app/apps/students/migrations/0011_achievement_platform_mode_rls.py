from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0010_achievement_enable_rls"),
    ]

    operations = [
        add_platform_mode_bypass("students_achievement"),
    ]
