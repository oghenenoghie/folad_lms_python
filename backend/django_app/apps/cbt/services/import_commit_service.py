"""Explicit, atomic commit of validated CBT source-import rows.

All question creation and import-ledger updates share one database transaction.
A failed commit therefore leaves the job retryable without orphaned questions.
"""
from django.db import transaction

from apps.cbt.models import CBTImportItem, CBTImportJob
from apps.cbt.services.import_job_service import transition_import_job
from apps.cbt.services.question_service import QuestionError, _bulk_import_payload, create_question


class ImportCommitError(ValueError):
    """A caller-correctable import commit conflict."""


@transaction.atomic
def commit_import_job(*, job_id: int, organization, actor) -> dict:
    """Create draft questions for every valid row, or create none.

    The job lock serializes concurrent commit requests. The per-item
    committed_question FK is also retained as an explicit retry checkpoint.
    Completed requests replay their persisted summary.
    """
    try:
        job = (
            CBTImportJob.objects.select_for_update()
            .select_related("organization", "subject", "class_level")
            .get(pk=job_id, organization_id=organization.pk)
        )
    except CBTImportJob.DoesNotExist:
        raise CBTImportJob.DoesNotExist

    if job.status == "completed":
        return dict(job.summary or {})

    if job.status == "validating":
        items = list(
            CBTImportItem.objects.select_for_update()
            .filter(job=job)
            .order_by("sequence")
        )
        if not items:
            raise ImportCommitError("the import has no extracted question rows")
        expected_total = (job.summary or {}).get("items_total")
        if expected_total is not None and expected_total != len(items):
            raise ImportCommitError("the extracted item ledger is incomplete; re-run extraction before committing")
        invalid = [item.sequence for item in items if item.validation_status != "valid"]
        if invalid:
            sample = ", ".join(str(value) for value in invalid[:10])
            suffix = "…" if len(invalid) > 10 else ""
            raise ImportCommitError(
                f"all rows must be valid before commit; invalid or pending rows: {sample}{suffix}"
            )
        if any(item.committed_question_id for item in items):
            raise ImportCommitError("the import ledger contains unexpected prior question commits")
        transition_import_job(
            job_id=job.pk,
            organization=organization,
            to_status="ready_to_commit",
            actor=actor,
        )
        job.refresh_from_db()
    elif job.status == "ready_to_commit":
        items = list(
            CBTImportItem.objects.select_for_update()
            .filter(job=job)
            .order_by("sequence")
        )
        if not items or any(item.validation_status != "valid" for item in items):
            raise ImportCommitError("the import is no longer eligible for commit")
    else:
        raise ImportCommitError(f"an import in {job.status!r} state cannot be committed")

    transition_import_job(
        job_id=job.pk,
        organization=organization,
        to_status="committing",
        actor=actor,
    )

    committed = 0
    for item in items:
        if item.committed_question_id:
            # This branch supports safe recovery if a future deployment
            # introduces a durable multi-transaction commit strategy.
            continue
        try:
            payload = _bulk_import_payload(subject=job.subject, row=item.payload)
        except (QuestionError, TypeError, ValueError) as exc:
            raise ImportCommitError(
                f"row {item.sequence} no longer passes question validation: {exc}"
            ) from exc
        payload["class_level"] = job.class_level
        question = create_question(
            organization=organization,
            actor=actor,
            **payload,
        )
        item.committed_question = question
        item.save(update_fields=["committed_question", "updated_at"])
        committed += 1

    summary = dict(job.summary or {})
    summary.update({
        "items_total": len(items),
        "items_valid": len(items),
        "items_invalid": 0,
        "items_committed": sum(1 for item in items if item.committed_question_id),
        "preview_only": False,
    })
    transition_import_job(
        job_id=job.pk,
        organization=organization,
        to_status="completed",
        actor=actor,
        summary=summary,
    )
    return summary
