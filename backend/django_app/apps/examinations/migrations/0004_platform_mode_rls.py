from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [
        ("examinations", "0003_enable_rls"),
    ]

    operations = [
        add_platform_mode_bypass("examinations_grading_scheme"),
        add_platform_mode_bypass("examinations_grade_band"),
        add_platform_mode_bypass("examinations_exam"),
        add_platform_mode_bypass("examinations_exam_schedule"),
        add_platform_mode_bypass("examinations_invigilator"),
        add_platform_mode_bypass("examinations_assessment"),
        add_platform_mode_bypass("examinations_result"),
        add_platform_mode_bypass("examinations_result_workflow_state"),
        add_platform_mode_bypass("examinations_report_card"),
    ]
