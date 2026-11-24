from django.db import migrations

CODES = [
    ("cbt_exams.view", "cbt_exams", "view", "View CBT exams"),
    ("cbt_exams.create", "cbt_exams", "create", "Create CBT exams"),
    ("cbt_exams.update", "cbt_exams", "update", "Update CBT exams"),
    ("cbt_exams.delete", "cbt_exams", "delete", "Delete CBT exams"),
    ("cbt_exams.publish", "cbt_exams", "publish", "Publish or archive a CBT exam"),
    ("cbt_exam_candidates.view", "cbt_exam_candidates", "view", "View CBT exam candidates"),
    ("cbt_exam_candidates.manage", "cbt_exam_candidates", "manage", "Assign or remove CBT exam candidates"),
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
        ("cbt", "0007_platform_mode_rls"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
