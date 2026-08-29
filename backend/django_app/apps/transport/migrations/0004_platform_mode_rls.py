from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [
        ("transport", "0003_enable_rls"),
    ]

    operations = [
        add_platform_mode_bypass("transport_vehicle"),
        add_platform_mode_bypass("transport_route"),
        add_platform_mode_bypass("transport_route_stop"),
        add_platform_mode_bypass("transport_assignment"),
        add_platform_mode_bypass("transport_vehicle_maintenance"),
    ]
