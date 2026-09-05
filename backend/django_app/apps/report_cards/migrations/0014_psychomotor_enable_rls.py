from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("report_cards", "0013_reportcard_overall_grade_reportcard_overall_remark_and_more"),
    ]

    operations = [
        enable_rls("report_cards_psychomotor_trait"),
        enable_rls("report_cards_psychomotor_rating"),
    ]
