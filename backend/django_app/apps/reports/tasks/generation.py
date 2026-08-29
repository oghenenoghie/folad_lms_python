"""Routed to the "reports" queue by config/celery.py's task_routes glob
(apps.*.tasks.reports.*)... except this module is apps.reports.tasks.generation,
which doesn't match that glob (it's "reports" the *app*, not a "tasks.reports"
module path), so it runs on the default queue — an export is no heavier than
a receipt or report-card PDF, which don't need a dedicated queue either.
"""
from celery import shared_task
from django.utils import timezone

from apps.core.storage import save_document
from apps.reports.models import ReportRequest
from apps.reports.services.exporters import CONTENT_TYPES, export_table
from apps.reports.services.generators import generate_table

_FILE_EXTENSIONS = {"csv": "csv", "xlsx": "xlsx", "pdf": "pdf"}


@shared_task
def generate_report(report_request_id: int) -> None:
    try:
        report_request = ReportRequest.objects.get(id=report_request_id)
    except ReportRequest.DoesNotExist:
        return

    report_request.status = "generating"
    report_request.save(update_fields=["status", "updated_at"])

    try:
        title, headers, rows = generate_table(
            report_type=report_request.report_type,
            school=report_request.school,
            parameters=report_request.parameters,
        )
        content = export_table(title=title, headers=headers, rows=rows, fmt=report_request.format)
        file_name = f"{report_request.report_type}.{_FILE_EXTENSIONS[report_request.format]}"
        storage_key = save_document(
            key_prefix=f"reports/{report_request.organization_id}",
            filename=file_name,
            content=content,
            content_type=CONTENT_TYPES[report_request.format],
        )
    except Exception as exc:  # noqa: BLE001 - report the failure onto the row, don't crash the worker
        report_request.status = "failed"
        report_request.error_message = str(exc)[:255]
        report_request.save(update_fields=["status", "error_message", "updated_at"])
        return

    report_request.status = "ready"
    report_request.storage_key = storage_key
    report_request.file_name = file_name
    report_request.content_type = CONTENT_TYPES[report_request.format]
    report_request.generated_at = timezone.now()
    report_request.error_message = ""
    report_request.save(
        update_fields=[
            "status", "storage_key", "file_name", "content_type", "generated_at",
            "error_message", "updated_at",
        ]
    )
