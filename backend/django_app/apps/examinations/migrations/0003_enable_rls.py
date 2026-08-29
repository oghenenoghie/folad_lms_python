from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("examinations", "0002_seed_permissions"),
    ]

    operations = [
        enable_rls("examinations_grading_scheme"),
        enable_rls("examinations_grade_band"),
        enable_rls("examinations_exam"),
        enable_rls("examinations_exam_schedule"),
        enable_rls("examinations_invigilator"),
        enable_rls("examinations_assessment"),
        enable_rls("examinations_result"),
        enable_rls("examinations_result_workflow_state"),
        enable_rls("examinations_report_card"),
    ]
