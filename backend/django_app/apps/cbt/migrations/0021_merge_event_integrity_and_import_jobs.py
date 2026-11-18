"""Merge the parallel CBT event-integrity and import-job migration branches."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("cbt", "0002_attempt_event_integrity"),
        ("cbt", "0020_seed_import_permissions"),
    ]

    operations = []
