from django.db import migrations

CODES = [
    ("inventory_items.view", "inventory_items", "view", "View inventory items"),
    ("inventory_items.create", "inventory_items", "create", "Create inventory items"),
    ("inventory_items.update", "inventory_items", "update", "Update inventory items"),
    ("inventory_items.delete", "inventory_items", "delete", "Delete inventory items"),
    ("suppliers.view", "suppliers", "view", "View suppliers"),
    ("suppliers.create", "suppliers", "create", "Create suppliers"),
    ("suppliers.update", "suppliers", "update", "Update suppliers"),
    ("suppliers.delete", "suppliers", "delete", "Delete suppliers"),
    ("purchase_orders.view", "purchase_orders", "view", "View purchase orders"),
    ("purchase_orders.create", "purchase_orders", "create", "Create purchase orders"),
    ("purchase_orders.update", "purchase_orders", "update", "Update or cancel purchase orders"),
    ("purchase_orders.delete", "purchase_orders", "delete", "Delete draft purchase orders"),
    ("purchase_orders.receive", "purchase_orders", "receive", "Receive purchase orders into stock"),
    ("stock_movements.view", "stock_movements", "view", "View stock movements"),
    ("stock_movements.create", "stock_movements", "create", "Record stock movements"),
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
        ("inventory", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
