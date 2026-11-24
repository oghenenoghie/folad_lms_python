from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [
        ("communication", "0003_enable_rls"),
    ]

    operations = [
        add_platform_mode_bypass("communication_announcement"),
        add_platform_mode_bypass("communication_notification"),
        add_platform_mode_bypass("communication_notification_preference"),
        add_platform_mode_bypass("communication_message"),
    ]
