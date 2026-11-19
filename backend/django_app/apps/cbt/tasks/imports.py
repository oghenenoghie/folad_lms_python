"""Background tasks for durable CBT source imports.

Tasks receive only a persisted job public ID and its organization ID. The
organization ID is used to establish the RLS context, then the job is fetched
again with both identifiers so a stale or malformed broker message cannot
cross tenant boundaries.
"""
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.cbt.models import CBTImportJob, CBTImportOutboxEvent
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


# Outbox publishing is intentionally independent of API requests. A beat
# scheduler invokes this task; every claim is short and tenant-scoped, while
# the broker call happens outside the database transaction.

_OUTBOX_EVENT_TYPE = "extract_source"
_OUTBOX_MAX_ATTEMPTS = 8
_OUTBOX_LEASE = timedelta(minutes=5)
_OUTBOX_BATCH_PER_ORG = 100


def _claim_outbox_event(*, organization_id: int, now):
    """Claim one due event under a row lock and return immutable publish data."""
    with transaction.atomic():
        event = (
            CBTImportOutboxEvent.objects.select_for_update(skip_locked=True)
            .select_related("job")
            .filter(
                Q(status="pending", available_at__lte=now)
                | Q(status="publishing", locked_at__lt=now - _OUTBOX_LEASE),
                organization_id=organization_id,
                event_type=_OUTBOX_EVENT_TYPE,
            )
            .order_by("available_at", "created_at", "pk")
            .first()
        )
        if event is None:
            return None
        if event.attempts >= _OUTBOX_MAX_ATTEMPTS:
            event.status = "failed"
            event.locked_at = None
            event.last_error = "MAX_PUBLISH_ATTEMPTS_EXCEEDED"
            event.save(update_fields=["status", "locked_at", "last_error", "updated_at"])
            return {"status": "exhausted"}

        claimed_at = now
        event.status = "publishing"
        event.attempts += 1
        event.locked_at = claimed_at
        event.last_error = ""
        event.save(update_fields=["status", "attempts", "locked_at", "last_error", "updated_at"])
        return {
            "event_id": event.pk,
            "organization_id": event.organization_id,
            "job_public_id": str(event.job.public_id),
            "claimed_at": claimed_at,
            "attempts": event.attempts,
        }


def _finish_outbox_publish(*, claim, error: bool = False):
    """Acknowledge a claim, or schedule a bounded retry without leaking errors."""
    with transaction.atomic():
        event = (
            CBTImportOutboxEvent.objects.select_for_update()
            .filter(
                pk=claim["event_id"],
                organization_id=claim["organization_id"],
                status="publishing",
                locked_at=claim["claimed_at"],
            )
            .first()
        )
        if event is None:
            # A newer lease owner has already reclaimed this event.
            return "claim_lost"

        now = timezone.now()
        if not error:
            event.status = "published"
            event.published_at = now
            event.locked_at = None
            event.last_error = ""
            event.save(update_fields=["status", "published_at", "locked_at", "last_error", "updated_at"])
            return "published"

        event.locked_at = None
        event.last_error = "BROKER_PUBLISH_FAILED"
        if event.attempts >= _OUTBOX_MAX_ATTEMPTS:
            event.status = "failed"
            event.save(update_fields=["status", "locked_at", "last_error", "updated_at"])
            return "failed"

        event.status = "pending"
        delay_seconds = min(30 * (2 ** (event.attempts - 1)), 900)
        event.available_at = now + timedelta(seconds=delay_seconds)
        event.save(
            update_fields=["status", "available_at", "locked_at", "last_error", "updated_at"]
        )
        return "retry_scheduled"


@shared_task(name="apps.cbt.tasks.imports.dispatch_pending_cbt_imports")
def dispatch_pending_cbt_imports() -> dict:
    """Publish due CBT import outbox events, safely across active tenants.

    Organization is a global tenancy boundary model. Each event query and
    state transition runs only after activating that organization's RLS
    context; this task never enables the platform-mode RLS bypass.
    """
    totals = {
        "organizations": 0,
        "claimed": 0,
        "published": 0,
        "retry_scheduled": 0,
        "failed": 0,
        "claim_lost": 0,
    }
    organization_ids = list(Organization.objects.filter(is_active=True).order_by("pk").values_list("pk", flat=True))
    try:
        for organization_id in organization_ids:
            totals["organizations"] += 1
            activate_organization(organization_id)
            try:
                for _ in range(_OUTBOX_BATCH_PER_ORG):
                    claim = _claim_outbox_event(
                        organization_id=organization_id,
                        now=timezone.now(),
                    )
                    if claim is None:
                        break
                    if claim.get("status") == "exhausted":
                        totals["failed"] += 1
                        continue

                    totals["claimed"] += 1
                    try:
                        extract_cbt_import_job.apply_async(
                            args=[claim["job_public_id"], claim["organization_id"]],
                            queue="imports",
                        )
                    except Exception:  # noqa: BLE001 - broker errors are retried with a safe code
                        outcome = _finish_outbox_publish(claim=claim, error=True)
                    else:
                        outcome = _finish_outbox_publish(claim=claim)

                    if outcome in totals:
                        totals[outcome] += 1
            finally:
                activate_organization(None)
    finally:
        activate_organization(None)

    return totals
