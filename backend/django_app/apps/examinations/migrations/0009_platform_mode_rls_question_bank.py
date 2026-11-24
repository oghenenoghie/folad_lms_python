from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [
        ("examinations", "0008_enable_rls_question_bank"),
    ]

    operations = [
        add_platform_mode_bypass("examinations_question"),
        add_platform_mode_bypass("examinations_question_option"),
        add_platform_mode_bypass("examinations_student_answer"),
    ]
