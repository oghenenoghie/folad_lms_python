from django.db import migrations

CODES = [
    ("staff.view", "staff", "view", "View staff"),
    ("staff.create", "staff", "create", "Create staff"),
    ("staff.update", "staff", "update", "Update staff"),
    ("staff.delete", "staff", "delete", "Delete staff"),
    ("teachers.view", "teachers", "view", "View teacher profiles"),
    ("teachers.create", "teachers", "create", "Create a teacher profile for a staff member"),
    ("teachers.update", "teachers", "update", "Update a teacher profile"),
    ("teachers.delete", "teachers", "delete", "Delete a teacher profile"),
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
        ("staff", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
