from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [("cbt", "0018_enable_import_rls")]

    operations = [
        add_platform_mode_bypass("cbt_import_job"),
        add_platform_mode_bypass("cbt_import_item"),
        add_platform_mode_bypass("cbt_import_issue"),
    ]
