from django.db import migrations

CODES = [
    ("vehicles.view", "vehicles", "view", "View vehicles"),
    ("vehicles.create", "vehicles", "create", "Create vehicles"),
    ("vehicles.update", "vehicles", "update", "Update vehicles"),
    ("vehicles.delete", "vehicles", "delete", "Delete vehicles"),
    ("transport_routes.view", "transport_routes", "view", "View transport routes"),
    ("transport_routes.create", "transport_routes", "create", "Create transport routes"),
    ("transport_routes.update", "transport_routes", "update", "Update transport routes"),
    ("transport_routes.delete", "transport_routes", "delete", "Delete transport routes"),
    ("route_stops.view", "route_stops", "view", "View route stops"),
    ("route_stops.create", "route_stops", "create", "Create route stops"),
    ("route_stops.update", "route_stops", "update", "Update route stops"),
    ("route_stops.delete", "route_stops", "delete", "Delete route stops"),
    ("transport_assignments.view", "transport_assignments", "view", "View transport assignments"),
    ("transport_assignments.create", "transport_assignments", "create", "Assign students to transport"),
    ("transport_assignments.delete", "transport_assignments", "delete", "Unassign students from transport"),
    ("vehicle_maintenance.view", "vehicle_maintenance", "view", "View vehicle maintenance records"),
    ("vehicle_maintenance.create", "vehicle_maintenance", "create", "Schedule vehicle maintenance"),
    ("vehicle_maintenance.update", "vehicle_maintenance", "update", "Update vehicle maintenance records"),
    ("vehicle_maintenance.delete", "vehicle_maintenance", "delete", "Delete vehicle maintenance records"),
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
        ("transport", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
