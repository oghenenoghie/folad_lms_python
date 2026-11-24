from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [
        ("library", "0003_enable_rls"),
    ]

    operations = [
        add_platform_mode_bypass("library_book"),
        add_platform_mode_bypass("library_copy"),
        add_platform_mode_bypass("library_member"),
        add_platform_mode_bypass("library_loan"),
        add_platform_mode_bypass("library_fine"),
    ]
