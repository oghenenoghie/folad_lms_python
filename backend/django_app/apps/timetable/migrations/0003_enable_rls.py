from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("timetable", "0002_seed_permissions"),
    ]

    operations = [
        enable_rls("timetable_room"),
        enable_rls("timetable_period"),
        enable_rls("timetable_slot"),
    ]
