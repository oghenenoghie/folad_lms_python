from django.db import migrations

CODES = [
    ("guardians.view", "guardians", "view", "View guardians"),
    ("guardians.create", "guardians", "create", "Create guardians"),
    ("guardians.update", "guardians", "update", "Update guardians"),
    ("guardians.delete", "guardians", "delete", "Delete guardians"),
    ("guardian_students.view", "guardian_students", "view", "View guardian-student links"),
    ("guardian_students.create", "guardian_students", "create", "Create guardian-student links"),
    ("guardian_students.update", "guardian_students", "update", "Update guardian-student links"),
    ("guardian_students.delete", "guardian_students", "delete", "Delete guardian-student links"),
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
        ("parents", "0002_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
