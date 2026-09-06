from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [
        ("cbt", "0002_enable_rls"),
    ]

    operations = [
        add_platform_mode_bypass("cbt_topic"),
        add_platform_mode_bypass("cbt_question"),
        add_platform_mode_bypass("cbt_question_block"),
        add_platform_mode_bypass("cbt_question_option"),
        add_platform_mode_bypass("cbt_question_version"),
        add_platform_mode_bypass("cbt_media"),
    ]
