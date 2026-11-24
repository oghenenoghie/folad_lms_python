from django.db import migrations

CODES = [
    ("documents.view", "documents", "view", "View documents"),
    ("documents.create", "documents", "create", "Upload documents"),
    ("documents.update", "documents", "update", "Update document metadata"),
    ("documents.delete", "documents", "delete", "Delete documents"),
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
        ("documents", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
