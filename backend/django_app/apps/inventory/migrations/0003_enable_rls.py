from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0002_seed_permissions"),
    ]

    operations = [
        enable_rls("inventory_item"),
        enable_rls("inventory_supplier"),
        enable_rls("inventory_purchase_order"),
        enable_rls("inventory_stock_movement"),
    ]
