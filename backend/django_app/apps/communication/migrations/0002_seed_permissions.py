from django.db import migrations

CODES = [
    ("announcements.view", "announcements", "view", "View announcements"),
    ("announcements.create", "announcements", "create", "Create announcements"),
    ("announcements.update", "announcements", "update", "Update or publish announcements"),
    ("announcements.delete", "announcements", "delete", "Delete announcements"),
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
        ("communication", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
