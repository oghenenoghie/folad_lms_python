from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0003_enable_rls"),
    ]

    operations = [
        add_platform_mode_bypass("academics_class_level"),
        add_platform_mode_bypass("academics_class_arm"),
        add_platform_mode_bypass("academics_subject"),
        add_platform_mode_bypass("academics_class_subject"),
        add_platform_mode_bypass("academics_enrollment"),
    ]
