from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("hostel", "0002_seed_permissions"),
    ]

    operations = [
        enable_rls("hostel_hostel"),
        enable_rls("hostel_building"),
        enable_rls("hostel_room"),
        enable_rls("hostel_bed"),
        enable_rls("hostel_allocation"),
        enable_rls("hostel_incident"),
    ]
