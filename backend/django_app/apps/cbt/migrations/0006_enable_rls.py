from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("cbt", "0005_exams"),
    ]

    operations = [
        enable_rls("cbt_exam"),
        enable_rls("cbt_exam_section"),
        enable_rls("cbt_exam_question"),
        enable_rls("cbt_exam_candidate"),
    ]
