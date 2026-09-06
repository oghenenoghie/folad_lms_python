from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("cbt", "0001_initial"),
    ]

    operations = [
        enable_rls("cbt_topic"),
        enable_rls("cbt_question"),
        enable_rls("cbt_question_block"),
        enable_rls("cbt_question_option"),
        enable_rls("cbt_question_version"),
        enable_rls("cbt_media"),
    ]
