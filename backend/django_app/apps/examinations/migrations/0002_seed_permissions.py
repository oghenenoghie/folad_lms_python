from django.db import migrations

CODES = [
    ("grading_schemes.view", "grading_schemes", "view", "View grading schemes"),
    ("grading_schemes.create", "grading_schemes", "create", "Create grading schemes"),
    ("grading_schemes.update", "grading_schemes", "update", "Update grading schemes"),
    ("grading_schemes.delete", "grading_schemes", "delete", "Delete grading schemes"),
    ("grade_bands.view", "grade_bands", "view", "View grade bands"),
    ("grade_bands.create", "grade_bands", "create", "Create grade bands"),
    ("grade_bands.update", "grade_bands", "update", "Update grade bands"),
    ("grade_bands.delete", "grade_bands", "delete", "Delete grade bands"),
    ("exams.view", "exams", "view", "View exams"),
    ("exams.create", "exams", "create", "Create exams"),
    ("exams.update", "exams", "update", "Update exams"),
    ("exams.delete", "exams", "delete", "Delete exams"),
    ("exam_schedules.view", "exam_schedules", "view", "View exam schedules"),
    ("exam_schedules.create", "exam_schedules", "create", "Create exam schedules"),
    ("exam_schedules.update", "exam_schedules", "update", "Update exam schedules"),
    ("exam_schedules.delete", "exam_schedules", "delete", "Delete exam schedules"),
    ("invigilators.view", "invigilators", "view", "View invigilators"),
    ("invigilators.create", "invigilators", "create", "Assign invigilators"),
    ("invigilators.delete", "invigilators", "delete", "Unassign invigilators"),
    ("assessments.view", "assessments", "view", "View assessments"),
    ("assessments.create", "assessments", "create", "Create assessments"),
    ("assessments.update", "assessments", "update", "Update assessments"),
    ("assessments.delete", "assessments", "delete", "Delete assessments"),
    ("results.view", "results", "view", "View results"),
    ("results.create", "results", "create", "Enter results"),
    ("results.update", "results", "update", "Correct results while entered"),
    ("results.delete", "results", "delete", "Delete results"),
    ("results.submit", "results", "submit", "Submit results for review"),
    ("results.review", "results", "review", "Review submitted results"),
    ("results.verify", "results", "verify", "Verify reviewed results"),
    ("results.publish", "results", "publish", "Publish verified results"),
    ("report_cards.view", "report_cards", "view", "View report cards"),
    ("report_cards.create", "report_cards", "create", "Request report card generation"),
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
        ("examinations", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
