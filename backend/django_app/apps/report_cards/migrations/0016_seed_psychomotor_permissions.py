from django.db import migrations

CODES = [
    ("psychomotor_traits.view", "psychomotor_traits", "view", "View psychomotor/affective traits"),
    ("psychomotor_traits.create", "psychomotor_traits", "create", "Create psychomotor/affective traits"),
    ("psychomotor_traits.update", "psychomotor_traits", "update", "Update psychomotor/affective traits"),
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
        ("report_cards", "0015_psychomotor_platform_mode_rls"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
