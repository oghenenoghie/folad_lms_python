from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("cbt", "0009_attempts"),
    ]

    operations = [
        enable_rls("cbt_exam_attempt"),
        enable_rls("cbt_student_answer"),
    ]
