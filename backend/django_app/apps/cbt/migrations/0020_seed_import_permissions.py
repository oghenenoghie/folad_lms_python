from django.db import migrations

CODES = [
    ("cbt_imports.create", "cbt_imports", "create", "Upload and create CBT import jobs"),
    ("cbt_imports.read", "cbt_imports", "read", "View CBT import jobs, items and issues"),
    ("cbt_imports.update", "cbt_imports", "update", "Update CBT import mappings"),
    ("cbt_imports.validate", "cbt_imports", "validate", "Validate CBT import jobs"),
    ("cbt_imports.commit", "cbt_imports", "commit", "Commit valid CBT import items as draft questions"),
    ("cbt_imports.cancel", "cbt_imports", "cancel", "Cancel CBT import jobs"),
]


def forwards(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    for code, module, action, description in CODES:
        Permission.objects.get_or_create(
            code=code,
            defaults={"module": module, "action": action, "description": description},
        )


def backwards(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Permission.objects.filter(code__in=[code for code, *_ in CODES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("cbt", "0019_import_platform_mode_rls"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
