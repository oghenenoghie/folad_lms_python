from django.db import migrations

from apps.tenancy.db import add_platform_mode_bypass


class Migration(migrations.Migration):
    dependencies = [
        ("reports", "0003_enable_rls"),
    ]

    operations = [
        add_platform_mode_bypass("reports_report_request"),
    ]
