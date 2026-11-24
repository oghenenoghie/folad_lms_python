from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [
        ("report_cards", "0010_reportcardaudit_enable_rls"),
    ]

    operations = [
        add_platform_mode_bypass("report_cards_report_card_audit"),
    ]
