from django.db import migrations

CODES = [
    ("attendance.view", "attendance", "view", "View attendance records"),
    ("attendance.create", "attendance", "create", "Mark attendance"),
    ("attendance.update", "attendance", "update", "Correct attendance records"),
    ("attendance.delete", "attendance", "delete", "Delete attendance records"),
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
        ("attendance", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
