from django.db import migrations

CODES = [
    ("students.view", "students", "view", "View students"),
    ("students.create", "students", "create", "Create students"),
    ("students.update", "students", "update", "Update students"),
    ("students.delete", "students", "delete", "Delete students"),
    ("student_guardians.view", "student_guardians", "view", "View student-guardian links"),
    ("student_guardians.create", "student_guardians", "create", "Link a guardian to a student"),
    ("student_guardians.update", "student_guardians", "update", "Update a student-guardian link"),
    ("student_guardians.delete", "student_guardians", "delete", "Unlink a guardian from a student"),
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
        ("students", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
