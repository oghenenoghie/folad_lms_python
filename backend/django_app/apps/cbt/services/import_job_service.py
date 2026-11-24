"""Transactional lifecycle operations for durable CBT source-import jobs.

This service deliberately does not enqueue Celery work. Dispatch belongs in
a later integration step after the production imports worker is deployed and
its health is verified.
"""
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone

from apps.cbt.models import CBTImportJob


class ImportJobError(ValueError):
    """A caller-correctable import workflow error."""


class InvalidImportJobTransition(ImportJobError):
    """The requested lifecycle transition is not permitted."""


# Keep this table explicit: terminal states have no outgoing transitions.
IMPORT_JOB_TRANSITIONS: dict[str, set[str]] = {
    "uploaded": {"queued", "cancelled"},
    "queued": {"extracting", "failed", "cancelled"},
    "extracting": {"needs_mapping", "validating", "failed", "cancelled"},
    "needs_mapping": {"queued", "validating", "failed", "cancelled"},
    "validating": {"needs_mapping", "ready_to_commit", "failed", "cancelled"},
    "ready_to_commit": {"committing", "cancelled"},
    "committing": {"completed", "completed_with_errors", "failed"},
    "completed": set(),
    "completed_with_errors": set(),
    "failed": set(),
    "cancelled": set(),
}

_TERMINAL_STATES = {"completed", "completed_with_errors", "failed", "cancelled"}
_ACTIVE_STATES = {"extracting", "validating", "committing"}


@transaction.atomic
def transition_import_job(
    *,
    job_id: int,
    organization,
    to_status: str,
    actor=None,
    summary: dict | None = None,
    failure_code: str = "",
    failure_message: str = "",
) -> CBTImportJob:
    """Lock and transition one job belonging to the supplied organization.

    Repeating the current status is an idempotent no-op. All other transitions
    are checked against the explicit state graph while the row lock is held.
    """
    if to_status not in IMPORT_JOB_TRANSITIONS:
        raise InvalidImportJobTransition(f"unknown import job status: {to_status!r}")

    try:
        job = (
            CBTImportJob.objects.select_for_update()
            .select_related("organization")
            .get(pk=job_id, organization_id=organization.pk)
        )
    except ObjectDoesNotExist as exc:
        # Do not reveal whether a job exists in another tenant.
        raise CBTImportJob.DoesNotExist from exc

    if job.status == to_status:
        return job

    allowed = IMPORT_JOB_TRANSITIONS.get(job.status, set())
    if to_status not in allowed:
        raise InvalidImportJobTransition(
            f"cannot move import job from {job.status!r} to {to_status!r}"
        )

    if to_status != "failed" and (failure_code or failure_message):
        raise ImportJobError("failure details may only be supplied when marking a job failed")

    now = timezone.now()
    job.status = to_status
    update_fields = ["status", "updated_at"]

    if to_status in _ACTIVE_STATES and job.started_at is None:
        job.started_at = now
        update_fields.append("started_at")

    if to_status in _TERMINAL_STATES:
        job.completed_at = now
        update_fields.append("completed_at")

    if to_status == "failed":
        job.failure_code = failure_code.strip()[:80]
        job.failure_message = failure_message.strip()
        update_fields.extend(["failure_code", "failure_message"])
    elif job.failure_code or job.failure_message:
        job.failure_code = ""
        job.failure_message = ""
        update_fields.extend(["failure_code", "failure_message"])

    if summary is not None:
        if not isinstance(summary, dict):
            raise ImportJobError("summary must be a JSON object")
        job.summary = summary
        update_fields.append("summary")

    if actor is not None:
        job.updated_by = actor
        update_fields.append("updated_by")

    job.save(update_fields=update_fields)
    return job
