from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [
        ("report_cards", "0014_psychomotor_enable_rls"),
    ]

    operations = [
        add_platform_mode_bypass("report_cards_psychomotor_trait"),
        add_platform_mode_bypass("report_cards_psychomotor_rating"),
    ]
