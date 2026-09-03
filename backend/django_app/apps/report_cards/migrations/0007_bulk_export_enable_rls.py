from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("report_cards", "0006_reportcardbulkexport"),
    ]

    operations = [
        enable_rls("report_cards_bulk_export"),
    ]
