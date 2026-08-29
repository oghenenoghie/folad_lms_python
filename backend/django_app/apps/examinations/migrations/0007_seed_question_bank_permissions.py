from django.db import migrations

CODES = [
    ("questions.view", "questions", "view", "View questions"),
    ("questions.create", "questions", "create", "Create questions"),
    ("questions.update", "questions", "update", "Update questions"),
    ("questions.delete", "questions", "delete", "Delete questions"),
    ("question_options.view", "question_options", "view", "View question options"),
    ("question_options.create", "question_options", "create", "Create question options"),
    ("question_options.update", "question_options", "update", "Update question options"),
    ("question_options.delete", "question_options", "delete", "Delete question options"),
    ("student_answers.view", "student_answers", "view", "View student answers"),
    ("student_answers.create", "student_answers", "create", "Submit student answers"),
    ("student_answers.delete", "student_answers", "delete", "Delete student answers"),
    ("student_answers.grade", "student_answers", "grade", "Grade subjective student answers"),
    ("results.finalize", "results", "finalize", "Finalize an assessment score from student answers"),
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
        ("examinations", "0006_question_bank"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
