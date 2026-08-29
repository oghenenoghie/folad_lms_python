from django.db import migrations

from apps.tenancy.db import make_append_only


class Migration(migrations.Migration):
    dependencies = [
        ("examinations", "0004_platform_mode_rls"),
    ]

    operations = [
        make_append_only("examinations_result_workflow_state"),
    ]
