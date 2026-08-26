from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0002_seed_permissions"),
    ]

    operations = [
        enable_rls("academics_class_level"),
        enable_rls("academics_class_arm"),
        enable_rls("academics_subject"),
        enable_rls("academics_class_subject"),
        enable_rls("academics_enrollment"),
    ]
