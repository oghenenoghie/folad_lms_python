from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0003_enable_rls"),
    ]

    operations = [
        add_platform_mode_bypass("finance_fee_structure"),
        add_platform_mode_bypass("finance_fee_item"),
        add_platform_mode_bypass("finance_discount"),
        add_platform_mode_bypass("finance_scholarship"),
        add_platform_mode_bypass("finance_invoice"),
        add_platform_mode_bypass("finance_invoice_line"),
        add_platform_mode_bypass("finance_payment"),
        add_platform_mode_bypass("finance_refund"),
        add_platform_mode_bypass("finance_receipt"),
        add_platform_mode_bypass("finance_ledger_entry"),
    ]
