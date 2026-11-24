from django.db import migrations

from apps.tenancy.db import make_append_only


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0004_platform_mode_rls"),
    ]

    operations = [
        make_append_only("inventory_stock_movement"),
    ]
