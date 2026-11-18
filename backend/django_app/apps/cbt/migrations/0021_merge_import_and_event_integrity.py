"""Join the parallel CBT migration leaves.

The attempt-event integrity migration and the M4-B import permission migration
both depend on the established CBT schema line. This no-op migration makes
their ordering explicit so Django has a single leaf and can validate drift.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("cbt", "0002_attempt_event_integrity"),
        ("cbt", "0020_seed_import_permissions"),
    ]

    operations = []
