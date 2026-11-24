from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("report_cards", "0002_seed_permissions"),
    ]

    operations = [
        enable_rls("report_cards_weighting"),
        enable_rls("report_cards_report_card"),
        enable_rls("report_cards_report_card_subject"),
    ]
