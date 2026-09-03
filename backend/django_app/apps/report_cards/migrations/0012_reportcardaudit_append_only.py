from django.db import migrations

from apps.tenancy.db import make_append_only


class Migration(migrations.Migration):
    dependencies = [
        ("report_cards", "0011_reportcardaudit_platform_mode_rls"),
    ]

    operations = [
        make_append_only("report_cards_report_card_audit"),
    ]
