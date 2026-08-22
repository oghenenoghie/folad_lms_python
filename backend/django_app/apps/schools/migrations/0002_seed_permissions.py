from django.db import migrations

CODES = [
    ("schools.view", "schools", "view", "View schools"),
    ("schools.create", "schools", "create", "Create schools"),
    ("schools.update", "schools", "update", "Update schools"),
    ("schools.delete", "schools", "delete", "Delete schools"),
    ("campuses.view", "campuses", "view", "View campuses"),
    ("campuses.create", "campuses", "create", "Create campuses"),
    ("campuses.update", "campuses", "update", "Update campuses"),
    ("campuses.delete", "campuses", "delete", "Delete campuses"),
    ("academic_years.view", "academic_years", "view", "View academic years"),
    ("academic_years.create", "academic_years", "create", "Create academic years"),
    ("academic_years.update", "academic_years", "update", "Update academic years"),
    ("academic_years.delete", "academic_years", "delete", "Delete academic years"),
    ("terms.view", "terms", "view", "View terms"),
    ("terms.create", "terms", "create", "Create terms"),
    ("terms.update", "terms", "update", "Update terms"),
    ("terms.delete", "terms", "delete", "Delete terms"),
    ("departments.view", "departments", "view", "View departments"),
    ("departments.create", "departments", "create", "Create departments"),
    ("departments.update", "departments", "update", "Update departments"),
    ("departments.delete", "departments", "delete", "Delete departments"),
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
        ("schools", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
