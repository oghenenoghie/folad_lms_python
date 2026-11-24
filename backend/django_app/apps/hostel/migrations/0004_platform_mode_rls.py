from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [
        ("hostel", "0003_enable_rls"),
    ]

    operations = [
        add_platform_mode_bypass("hostel_hostel"),
        add_platform_mode_bypass("hostel_building"),
        add_platform_mode_bypass("hostel_room"),
        add_platform_mode_bypass("hostel_bed"),
        add_platform_mode_bypass("hostel_allocation"),
        add_platform_mode_bypass("hostel_incident"),
    ]
