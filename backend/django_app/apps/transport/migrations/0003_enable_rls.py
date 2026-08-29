from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("transport", "0002_seed_permissions"),
    ]

    operations = [
        enable_rls("transport_vehicle"),
        enable_rls("transport_route"),
        enable_rls("transport_route_stop"),
        enable_rls("transport_assignment"),
        enable_rls("transport_vehicle_maintenance"),
    ]
