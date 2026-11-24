from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [
        ("schools", "0003_enable_rls"),
    ]

    operations = [
        add_platform_mode_bypass("schools_school"),
        add_platform_mode_bypass("schools_campus"),
        add_platform_mode_bypass("schools_academic_year"),
        add_platform_mode_bypass("schools_term"),
        add_platform_mode_bypass("schools_department"),
    ]
