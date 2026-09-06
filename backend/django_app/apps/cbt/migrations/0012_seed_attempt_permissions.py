from django.db import migrations

CODES = [
    ("cbt_attempts.view", "cbt_attempts", "view", "View every candidate's CBT exam attempts (staff)"),
    ("cbt_attempts.grade", "cbt_attempts", "grade", "Manually grade subjective CBT answers"),
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
        ("cbt", "0011_platform_mode_rls"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
