"""Join duplicate no-op CBT migration leaves introduced during reconciliation.

Both parent migrations preserve the same schema state: one joins the original
attempt-event integrity migration to the import-job chain, while the other
repeats that join under a second migration name. This final no-op node makes
Django's migration graph unambiguous without changing database schema or data.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("cbt", "0021_merge_event_integrity_and_import_jobs"),
        ("cbt", "0021_merge_import_and_event_integrity"),
    ]

    operations = []
