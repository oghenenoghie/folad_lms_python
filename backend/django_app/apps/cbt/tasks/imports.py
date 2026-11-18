"""Background tasks for durable CBT source imports.

Tasks receive only a persisted job public ID and its organization ID. The
organization ID is used to establish the RLS context, then the job is fetched
again with both identifiers so a stale or malformed broker message cannot
cross tenant boundaries.
"""
from celery import shared_task
from django.db import transaction

from apps.cbt.models import CBTImportJob
from apps.cbt.services.import_extraction_service import (
    ImportExtractionError,
    extract_import_job,
)
from apps.cbt.services.import_job_service import (
    InvalidImportJobTransition,
    transition_import_job,
)
from apps.tenancy.context import activate_organization
from apps.tenancy.models import Organization

_TERMINAL_STATUSES = {
    "completed", "completed_with_errors", "failed", "cancelled",
}
_PROCESSABLE_STATUSES = {"uploaded", "queued", "validating"}
_SAFE_FAILURE_CODE = "EXTRACTION_FAILED"
_SAFE_FAILURE_MESSAGE = "The source could not be processed. Check the file and try again."


def _mark_extraction_failed(*, job_id: int, organization) -> str:
    """Persist a safe failure state without overwriting cancellation/terminal states."""
    with transaction.atomic():
        try:
            job = CBTImportJob.objects.select_for_update().get(
                pk=job_id, organization_id=organization.pk
            )
        except CBTImportJob.DoesNotExist:
            return "not_found"

        if job.status == "uploaded":
            transition_import_job(
                job_id=job.pk, organization=organization, to_status="queued"
            )
            job.refresh_from_db()
        if job.status in {"queued", "extracting", "validating"}:
            try:
                failed = transition_import_job(
                    job_id=job.pk,
                    organization=organization,
                    to_status="failed",
                    failure_code=_SAFE_FAILURE_CODE,
                    failure_message=_SAFE_FAILURE_MESSAGE,
                )
                return failed.status
            except InvalidImportJobTransition:
                # Cancellation or another terminal transition won the race.
                job.refresh_from_db()
        return job.status


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def extract_cbt_import_job(self, job_public_id: str, organization_id: int) -> dict:
    """Extract one uploaded CSV/XLSX import into its durable preview ledger.

    Duplicate delivery is safe: the extraction service locks the job and
    returns the persisted summary when a prior delivery already completed.
    Transient/unexpected failures receive bounded Celery retries; deterministic
    extraction failures are recorded as a generic, non-sensitive job failure.
    """
    try:
        organization_id = int(organization_id)
        if organization_id < 1:
            return {"status": "not_found"}

        # A worker starts with no request-scoped tenant context. The broker
        # message supplies only the tenant locator; the job lookup below must
        # independently confirm ownership before any source is read.
        activate_organization(organization_id)
        organization = Organization.objects.filter(
            pk=organization_id, is_active=True
        ).first()
        if organization is None:
            return {"status": "not_found"}

        job = CBTImportJob.objects.filter(
            public_id=job_public_id,
            organization_id=organization_id,
        ).first()
        if job is None:
            return {"status": "not_found"}
        if job.status in _TERMINAL_STATUSES:
            return {"status": job.status, "summary": dict(job.summary or {})}
        if job.status not in _PROCESSABLE_STATUSES:
            return {"status": job.status, "summary": dict(job.summary or {})}

        try:
            summary = extract_import_job(
                job_id=job.pk,
                organization=organization,
            )
        except ImportExtractionError:
            status = _mark_extraction_failed(job_id=job.pk, organization=organization)
            return {"status": status}
        except Exception as exc:  # noqa: BLE001 - bounded retry for infrastructure/parser surprises
            if self.request.retries < self.max_retries:
                raise self.retry(
                    exc=exc,
                    countdown=min(30 * (2 ** self.request.retries), 300),
                )
            status = _mark_extraction_failed(job_id=job.pk, organization=organization)
            return {"status": status}

        return {"status": "validating", "summary": summary}
    finally:
        # Celery reuses worker processes and database connections. Never let
        # this task's tenant GUC/context leak into the next task on the worker.
        activate_organization(None)
