from django.db import migrations

CODES = [
    ("rooms.view", "rooms", "view", "View rooms"),
    ("rooms.create", "rooms", "create", "Create rooms"),
    ("rooms.update", "rooms", "update", "Update rooms"),
    ("rooms.delete", "rooms", "delete", "Delete rooms"),
    ("periods.view", "periods", "view", "View periods"),
    ("periods.create", "periods", "create", "Create periods"),
    ("periods.update", "periods", "update", "Update periods"),
    ("periods.delete", "periods", "delete", "Delete periods"),
    ("timetable_slots.view", "timetable_slots", "view", "View timetable slots"),
    ("timetable_slots.create", "timetable_slots", "create", "Create timetable slots"),
    ("timetable_slots.update", "timetable_slots", "update", "Update timetable slots"),
    ("timetable_slots.delete", "timetable_slots", "delete", "Delete timetable slots"),
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
        ("timetable", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
