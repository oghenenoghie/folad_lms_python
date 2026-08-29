from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0003_enable_rls"),
    ]

    operations = [
        add_platform_mode_bypass("inventory_item"),
        add_platform_mode_bypass("inventory_supplier"),
        add_platform_mode_bypass("inventory_purchase_order"),
        add_platform_mode_bypass("inventory_stock_movement"),
    ]
