from django.db import migrations

CODES = [
    ("hostels.view", "hostels", "view", "View hostels"),
    ("hostels.create", "hostels", "create", "Create hostels"),
    ("hostels.update", "hostels", "update", "Update hostels"),
    ("hostels.delete", "hostels", "delete", "Delete hostels"),
    ("hostel_buildings.view", "hostel_buildings", "view", "View hostel buildings"),
    ("hostel_buildings.create", "hostel_buildings", "create", "Create hostel buildings"),
    ("hostel_buildings.update", "hostel_buildings", "update", "Update hostel buildings"),
    ("hostel_buildings.delete", "hostel_buildings", "delete", "Delete hostel buildings"),
    ("hostel_rooms.view", "hostel_rooms", "view", "View hostel rooms"),
    ("hostel_rooms.create", "hostel_rooms", "create", "Create hostel rooms"),
    ("hostel_rooms.update", "hostel_rooms", "update", "Update hostel rooms"),
    ("hostel_rooms.delete", "hostel_rooms", "delete", "Delete hostel rooms"),
    ("hostel_beds.view", "hostel_beds", "view", "View hostel beds"),
    ("hostel_beds.create", "hostel_beds", "create", "Create hostel beds"),
    ("hostel_beds.update", "hostel_beds", "update", "Update hostel beds"),
    ("hostel_beds.delete", "hostel_beds", "delete", "Delete hostel beds"),
    ("hostel_allocations.view", "hostel_allocations", "view", "View hostel allocations"),
    ("hostel_allocations.create", "hostel_allocations", "create", "Allocate hostel beds"),
    ("hostel_allocations.update", "hostel_allocations", "update", "Vacate hostel beds"),
    ("hostel_incidents.view", "hostel_incidents", "view", "View hostel incidents"),
    ("hostel_incidents.create", "hostel_incidents", "create", "Report hostel incidents"),
    ("hostel_incidents.update", "hostel_incidents", "update", "Update or resolve hostel incidents"),
    ("hostel_incidents.delete", "hostel_incidents", "delete", "Delete hostel incidents"),
]


def forwards(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    for code, module, action, description in CODES:
        Permission.objects.get_or_create(
            code=code, defaults={"module": module, "action": action, "description": description}
        )


def backwards(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Permission.objects.filter(code__in=[code for code, *_ in CODES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("hostel", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
