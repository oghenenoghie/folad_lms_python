from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [
        ("cbt", "0006_enable_rls"),
    ]

    operations = [
        add_platform_mode_bypass("cbt_exam"),
        add_platform_mode_bypass("cbt_exam_section"),
        add_platform_mode_bypass("cbt_exam_question"),
        add_platform_mode_bypass("cbt_exam_candidate"),
    ]
