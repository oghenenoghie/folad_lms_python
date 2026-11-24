from django.db import migrations

CODES = [
    ("cbt_topics.view", "cbt_topics", "view", "View CBT topics"),
    ("cbt_topics.create", "cbt_topics", "create", "Create CBT topics"),
    ("cbt_topics.update", "cbt_topics", "update", "Update CBT topics"),
    ("cbt_topics.delete", "cbt_topics", "delete", "Delete CBT topics"),
    ("cbt_questions.view", "cbt_questions", "view", "View CBT questions"),
    ("cbt_questions.create", "cbt_questions", "create", "Create CBT questions"),
    ("cbt_questions.update", "cbt_questions", "update", "Update CBT questions"),
    ("cbt_questions.delete", "cbt_questions", "delete", "Delete CBT questions"),
    ("cbt_questions.submit", "cbt_questions", "submit", "Submit a CBT question for review"),
    ("cbt_questions.review", "cbt_questions", "review", "Move a submitted CBT question into review"),
    ("cbt_questions.approve", "cbt_questions", "approve", "Approve or reject a reviewed CBT question"),
    ("cbt_questions.publish", "cbt_questions", "publish", "Publish or archive an approved CBT question"),
    ("cbt_media.view", "cbt_media", "view", "View the CBT media library"),
    ("cbt_media.upload", "cbt_media", "upload", "Upload CBT media"),
    ("cbt_media.delete", "cbt_media", "delete", "Delete CBT media"),
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
        ("cbt", "0003_platform_mode_rls"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
