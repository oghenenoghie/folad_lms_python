from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("cbt", "0014_examattempt_flagged_for_review_examattemptevent"),
    ]

    operations = [
        enable_rls("cbt_exam_attempt_event"),
    ]
