"""Extract uploaded CSV/XLSX sources into a durable, validated import ledger.

This stage never creates Question records. It records canonical row payloads,
item-level diagnostics, and deterministic fingerprints so preview/retry is safe.
"""
import csv
import hashlib
import io
import json
from decimal import Decimal

from django.db import transaction

from apps.cbt.models import CBTImportIssue, CBTImportItem, CBTImportJob
from apps.cbt.services.import_job_service import transition_import_job
from apps.cbt.services.question_service import QuestionError, _bulk_import_payload

MAX_PREVIEW_ITEMS = 5000


class ImportExtractionError(ValueError):
    """The source cannot be extracted or the job is not ready for extraction."""


def _read_rows(*, content: bytes, source_format: str) -> list[dict]:
    if source_format == "csv":
        try:
            text = content.decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
            if not reader.fieldnames:
                raise ImportExtractionError("CSV header row is missing")
            headers = [str(value).strip().lower() for value in reader.fieldnames]
            if len(set(headers)) != len(headers) or any(not value for value in headers):
                raise ImportExtractionError("CSV headers must be non-empty and unique")
            rows = []
            for number, raw in enumerate(reader, start=1):
                if number > MAX_PREVIEW_ITEMS:
                    raise ImportExtractionError("source exceeds the 5,000 question limit")
                rows.append({str(key).strip().lower(): value for key, value in raw.items() if key is not None})
            return rows
        except (UnicodeDecodeError, csv.Error) as exc:
            raise ImportExtractionError("CSV could not be decoded or parsed") from exc

    if source_format == "xlsx":
        try:
            from openpyxl import load_workbook

            workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            try:
                sheet = workbook.active
                iterator = sheet.iter_rows(values_only=True)
                raw_headers = next(iterator, ())
                headers = [str(value).strip().lower() if value is not None else "" for value in raw_headers]
                while headers and not headers[-1]:
                    headers.pop()
                if not headers or any(not value for value in headers) or len(set(headers)) != len(headers):
                    raise ImportExtractionError("worksheet headers must be non-empty and unique")
                rows = []
                for number, values in enumerate(iterator, start=1):
                    if number > MAX_PREVIEW_ITEMS:
                        raise ImportExtractionError("source exceeds the 5,000 question limit")
                    values = list(values[:len(headers)])
                    if not any(value is not None for value in values):
                        continue
                    values.extend([None] * (len(headers) - len(values)))
                    rows.append({header: value for header, value in zip(headers, values)})
                return rows
            finally:
                workbook.close()
        except ImportExtractionError:
            raise
        except Exception as exc:
            raise ImportExtractionError("XLSX worksheet could not be parsed") from exc

    raise ImportExtractionError("only CSV and XLSX extraction is currently supported")


def _json_value(value):
    """Convert spreadsheet scalars to stable JSON-safe text values.

    The question service expects textual stems/options/codes; Excel often
    returns numeric cells as int/float, which must not reach .strip() calls.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


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
        rows = _read_rows(content=content, source_format=job.source_format)
        if not rows:
            raise ImportExtractionError("source contains no question rows")

        items = []
        issues = []
        valid_count = 0
        for sequence, row in enumerate(rows, start=1):
            normalized = {str(key).strip().lower(): _json_value(value) for key, value in row.items()}
            fingerprint_input = json.dumps(
                {"source": job.source_sha256, "sequence": sequence, "row": normalized},
                sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            )
            fingerprint = hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()
            try:
                _bulk_import_payload(subject=job.subject, row=normalized)
                validation_status = "valid"
                valid_count += 1
                error_message = None
            except (QuestionError, ValueError, TypeError) as exc:
                validation_status = "invalid"
                error_message = str(exc)[:2000]

            item = CBTImportItem(
                organization=organization,
                job=job,
                sequence=sequence,
                source_locator={"row": sequence + 1, "sheet": "active" if job.source_format == "xlsx" else None},
                source_fingerprint=fingerprint,
                payload=normalized,
                validation_status=validation_status,
            )
            items.append(item)
            if error_message:
                issues.append(CBTImportIssue(
                    organization=organization,
                    job=job,
                    severity="error",
                    code="ROW_VALIDATION_FAILED",
                    message=error_message,
                    source_locator={"row": sequence + 1},
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
