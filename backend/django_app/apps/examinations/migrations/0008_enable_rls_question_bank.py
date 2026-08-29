from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("examinations", "0007_seed_question_bank_permissions"),
    ]

    operations = [
        enable_rls("examinations_question"),
        enable_rls("examinations_question_option"),
        enable_rls("examinations_student_answer"),
    ]
