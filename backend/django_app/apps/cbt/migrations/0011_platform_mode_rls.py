from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [
        ("cbt", "0010_enable_rls"),
    ]

    operations = [
        add_platform_mode_bypass("cbt_exam_attempt"),
        add_platform_mode_bypass("cbt_student_answer"),
    ]
