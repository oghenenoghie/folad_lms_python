"""Purge expired private source objects for terminal CBT imports.

Run without flags to preview. Pass --execute only after reviewing the
candidate count; the database ledger is retained after object deletion.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.cbt.models import CBTImportJob
from apps.core.storage import delete_document
from apps.tenancy.context import activate_organization
from apps.tenancy.models import Organization

RETENTION_DAYS = 30
TERMINAL_STATUSES = ("completed", "completed_with_errors", "failed", "cancelled")


class Command(BaseCommand):
    help = "Preview or purge CBT source objects retained beyond 30 days after job completion."

    def add_arguments(self, parser):
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Delete expired source objects. Without this flag the command is dry-run only.",
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=RETENTION_DAYS)
        execute = options["execute"]
        candidates = 0
        deleted = 0
        failed = 0

        try:
            for organization_id in Organization.objects.filter(is_active=True).values_list("pk", flat=True):
                activate_organization(organization_id)
                jobs = CBTImportJob.objects.filter(
                    status__in=TERMINAL_STATUSES,
                    completed_at__lte=cutoff,
                ).exclude(storage_key="")
                for job_id in jobs.values_list("pk", flat=True).iterator():
                    candidates += 1
                    if not execute:
                        continue
                    try:
                        with transaction.atomic():
                            job = CBTImportJob.objects.select_for_update().get(pk=job_id)
                            if (
                                job.status not in TERMINAL_STATUSES
                                or job.completed_at is None
                                or job.completed_at > cutoff
                                or not job.storage_key
                            ):
                                continue
                            delete_document(job.storage_key)
                            job.storage_key = ""
                            job.save(update_fields=["storage_key", "updated_at"])
                            deleted += 1
                    except Exception as exc:
                        failed += 1
                        self.stderr.write(
                            self.style.ERROR(f"Import job {job_id}: source deletion failed ({type(exc).__name__})")
                        )
        finally:
            activate_organization(None)

        mode = "Executed" if execute else "Dry run"
        self.stdout.write(
            f"{mode}: {candidates} expired source(s) found; {deleted} deleted; {failed} failed."
        )
        if not execute:
            self.stdout.write("No objects were deleted. Re-run with --execute to apply the purge.")
