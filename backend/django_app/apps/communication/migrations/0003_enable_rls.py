from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("communication", "0002_seed_permissions"),
    ]

    operations = [
        enable_rls("communication_announcement"),
        enable_rls("communication_notification"),
        enable_rls("communication_notification_preference"),
        enable_rls("communication_message"),
    ]
