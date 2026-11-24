from django.db import migrations

CODES = [
    ("assignments.view", "assignments", "view", "View assignments"),
    ("assignments.create", "assignments", "create", "Create assignments"),
    ("assignments.update", "assignments", "update", "Update assignments"),
    ("assignments.delete", "assignments", "delete", "Delete assignments"),
    ("assignment_submissions.view", "assignment_submissions", "view", "View assignment submissions"),
    ("assignment_submissions.create", "assignment_submissions", "create", "Submit assignments"),
    ("assignment_submissions.update", "assignment_submissions", "update", "Grade assignment submissions"),
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
        ("assignments", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
