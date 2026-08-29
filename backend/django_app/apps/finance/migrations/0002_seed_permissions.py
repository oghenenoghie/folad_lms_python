from django.db import migrations

CODES = [
    ("fee_structures.view", "fee_structures", "view", "View fee structures"),
    ("fee_structures.create", "fee_structures", "create", "Create fee structures"),
    ("fee_structures.update", "fee_structures", "update", "Update fee structures"),
    ("fee_structures.delete", "fee_structures", "delete", "Delete fee structures"),
    ("fee_items.view", "fee_items", "view", "View fee items"),
    ("fee_items.create", "fee_items", "create", "Create fee items"),
    ("fee_items.update", "fee_items", "update", "Update fee items"),
    ("fee_items.delete", "fee_items", "delete", "Delete fee items"),
    ("discounts.view", "discounts", "view", "View discounts"),
    ("discounts.create", "discounts", "create", "Create discounts"),
    ("discounts.update", "discounts", "update", "Update discounts"),
    ("discounts.delete", "discounts", "delete", "Delete discounts"),
    ("scholarships.view", "scholarships", "view", "View scholarships"),
    ("scholarships.create", "scholarships", "create", "Award scholarships"),
    ("scholarships.update", "scholarships", "update", "Update scholarships"),
    ("scholarships.delete", "scholarships", "delete", "Revoke scholarships"),
    ("invoices.view", "invoices", "view", "View invoices"),
    ("invoices.create", "invoices", "create", "Create invoices"),
    ("invoices.update", "invoices", "update", "Update draft invoices"),
    ("invoices.delete", "invoices", "delete", "Delete draft invoices"),
    ("invoices.issue", "invoices", "issue", "Issue invoices"),
    ("invoices.cancel", "invoices", "cancel", "Cancel invoices"),
    ("invoice_lines.view", "invoice_lines", "view", "View invoice lines"),
    ("invoice_lines.create", "invoice_lines", "create", "Add invoice lines"),
    ("invoice_lines.update", "invoice_lines", "update", "Update invoice lines"),
    ("invoice_lines.delete", "invoice_lines", "delete", "Remove invoice lines"),
    ("payments.view", "payments", "view", "View payments"),
    ("payments.create", "payments", "create", "Record payments"),
    ("refunds.view", "refunds", "view", "View refunds"),
    ("refunds.create", "refunds", "create", "Issue refunds"),
    ("receipts.view", "receipts", "view", "View receipts"),
    ("ledger_entries.view", "ledger_entries", "view", "View ledger entries"),
]


def forwards(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    for code, module, action, description in CODES:
        Permission.objects.get_or_create(
            code=code, defaults={"module": module, "action": action, "description": description}
        )


def backwards(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Permission.objects.filter(code__in=[code for code, *_ in CODES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
