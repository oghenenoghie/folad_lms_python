from django.db import migrations

from apps.tenancy.db import enable_rls


class Migration(migrations.Migration):
    dependencies = [("cbt", "0017_cbt_import_jobs")]

    operations = [
        enable_rls("cbt_import_job"),
        enable_rls("cbt_import_item"),
        enable_rls("cbt_import_issue"),
    ]
