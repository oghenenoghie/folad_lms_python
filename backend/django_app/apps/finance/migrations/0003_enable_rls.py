from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0002_seed_permissions"),
    ]

    operations = [
        enable_rls("finance_fee_structure"),
        enable_rls("finance_fee_item"),
        enable_rls("finance_discount"),
        enable_rls("finance_scholarship"),
        enable_rls("finance_invoice"),
        enable_rls("finance_invoice_line"),
        enable_rls("finance_payment"),
        enable_rls("finance_refund"),
        enable_rls("finance_receipt"),
        enable_rls("finance_ledger_entry"),
    ]
