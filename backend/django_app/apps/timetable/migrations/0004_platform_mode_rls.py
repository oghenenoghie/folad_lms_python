from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [
        ("timetable", "0003_enable_rls"),
    ]

    operations = [
        add_platform_mode_bypass("timetable_room"),
        add_platform_mode_bypass("timetable_period"),
        add_platform_mode_bypass("timetable_slot"),
    ]
