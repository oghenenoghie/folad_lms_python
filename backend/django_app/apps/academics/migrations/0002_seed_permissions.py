from django.db import migrations

CODES = [
    ("class_levels.view", "class_levels", "view", "View class levels"),
    ("class_levels.create", "class_levels", "create", "Create class levels"),
    ("class_levels.update", "class_levels", "update", "Update class levels"),
    ("class_levels.delete", "class_levels", "delete", "Delete class levels"),
    ("class_arms.view", "class_arms", "view", "View class arms"),
    ("class_arms.create", "class_arms", "create", "Create class arms"),
    ("class_arms.update", "class_arms", "update", "Update class arms"),
    ("class_arms.delete", "class_arms", "delete", "Delete class arms"),
    ("subjects.view", "subjects", "view", "View subjects"),
    ("subjects.create", "subjects", "create", "Create subjects"),
    ("subjects.update", "subjects", "update", "Update subjects"),
    ("subjects.delete", "subjects", "delete", "Delete subjects"),
    ("class_subjects.view", "class_subjects", "view", "View class-subject assignments"),
    ("class_subjects.create", "class_subjects", "create", "Create class-subject assignments"),
    ("class_subjects.update", "class_subjects", "update", "Update class-subject assignments"),
    ("class_subjects.delete", "class_subjects", "delete", "Delete class-subject assignments"),
    ("enrollments.view", "enrollments", "view", "View enrollments"),
    ("enrollments.create", "enrollments", "create", "Create enrollments"),
    ("enrollments.update", "enrollments", "update", "Update enrollments"),
    ("enrollments.delete", "enrollments", "delete", "Delete enrollments"),
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
        ("academics", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
