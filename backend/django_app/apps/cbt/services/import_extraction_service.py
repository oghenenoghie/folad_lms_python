"""Extract uploaded CSV/XLSX sources into a durable, validated import ledger.

This stage never creates Question records. It records canonical row payloads,
item-level diagnostics, and deterministic fingerprints so preview/retry is safe.
"""
from django.db import transaction

from apps.cbt.models import CBTImportIssue, CBTImportItem, CBTImportJob
from apps.cbt.services.import_job_service import transition_import_job
from apps.cbt.services.question_service import QuestionError, _bulk_import_payload
from apps.cbt.services.source_extraction_service import (
    SourceExtractionError,
    extract_source_rows,
)

MAX_PREVIEW_ITEMS = 5000


class ImportExtractionError(ValueError):
    """The source cannot be extracted or the job is not ready for extraction."""


def _extract_rows(*, content: bytes, source_format: str):
    """Use the canonical parser so persisted locators match the source exactly."""
    try:
        return extract_source_rows(content=content, source_format=source_format)
    except SourceExtractionError as exc:
        raise ImportExtractionError(str(exc)) from exc


def extract_import_job(*, job_id: int, organization, actor=None) -> dict:
    """Extract one tenant-owned uploaded job into CBTImportItem/Issue rows.

    The job is locked for the full operation. Replays after extraction return
    the persisted summary and never duplicate items or issues. No question
    bank records are written in this stage.
    """
    from apps.core.storage import get_file_bytes

    with transaction.atomic():
        try:
            job = CBTImportJob.objects.select_for_update().get(
                pk=job_id, organization_id=organization.pk
            )
        except CBTImportJob.DoesNotExist:
            raise CBTImportJob.DoesNotExist

        if job.status == "validating" and job.items.exists():
            return dict(job.summary or {})
        if job.status == "uploaded":
            transition_import_job(job_id=job.pk, organization=organization, to_status="queued", actor=actor)
            job.refresh_from_db()
        if job.status == "queued":
            transition_import_job(job_id=job.pk, organization=organization, to_status="extracting", actor=actor)
            job.refresh_from_db()
        if job.status != "extracting":
            raise ImportExtractionError(f"job in {job.status!r} state cannot be extracted")

        content = get_file_bytes(job.storage_key)
        if content is None:
            raise ImportExtractionError("private source file is unavailable")
        rows = _extract_rows(content=content, source_format=job.source_format)
        if not rows:
            raise ImportExtractionError("source contains no question rows")
        if len(rows) > MAX_PREVIEW_ITEMS:
            raise ImportExtractionError(f"source exceeds the {MAX_PREVIEW_ITEMS:,} question limit")

        items = []
        issues = []
        valid_count = 0
        for extracted in rows:
            normalized = extracted.payload
            try:
                _bulk_import_payload(subject=job.subject, row=normalized)
                validation_status = "valid"
                valid_count += 1
                error_message = None
            except (QuestionError, ValueError, TypeError) as exc:
                validation_status = "invalid"
                error_message = str(exc)[:2000]

            items.append(CBTImportItem(
                organization=organization,
                job=job,
                sequence=extracted.sequence,
                source_locator=extracted.source_locator,
                source_fingerprint=extracted.source_fingerprint,
                payload=normalized,
                validation_status=validation_status,
            ))
            if error_message:
                issues.append(CBTImportIssue(
                    organization=organization,
                    job=job,
                    severity="error",
                    code="ROW_VALIDATION_FAILED",
                    message=error_message,
                    source_locator=extracted.source_locator,
                ))

        CBTImportItem.objects.bulk_create(items, batch_size=500)
        CBTImportIssue.objects.bulk_create(issues, batch_size=500)
        summary = {
            "items_total": len(items),
            "items_valid": valid_count,
            "items_invalid": len(items) - valid_count,
            "items_committed": 0,
            "preview_only": True,
        }
        transition_import_job(
            job_id=job.pk, organization=organization, to_status="validating",
            actor=actor, summary=summary,
        )
        return summary
