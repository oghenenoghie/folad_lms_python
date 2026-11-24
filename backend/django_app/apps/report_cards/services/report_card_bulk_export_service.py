"""Async "generate every report card for a term (or one class arm) and
hand back a ZIP of every resulting PDF" — the whole-school-scale sibling
report_card_service.generate_report_cards_bulk's own docstring flags as
deferred ("a real 'generate for the whole school' run belongs on a Celery
queue... that's a later phase"). This module is that later phase.

Two-step split, same shape as the single-report-card PDF job
(ReportCard.pdf_status / tasks.reports.generate_report_card_pdf):
`request_bulk_export` runs in the request cycle and only ever creates a
tracking row + enqueues a task, so a whole-school run can never block or
time out an HTTP request; `run_bulk_export` does the actual work inside
the Celery worker.

Each PDF is rendered directly here via render_report_card_pdf rather than
by waiting on the individual ReportCard.pdf_status jobs
generate_report_card (called internally by generate_report_cards_bulk)
already enqueues for each row — coordinating with those separate,
independently-scheduled tasks would need a Celery chord for no real
benefit, since rendering a report card's PDF a second time here is cheap
and keeps this job self-contained.
"""
import io
import zipfile

from django.db import transaction
from django.utils import timezone

from apps.core.storage import save_file
from apps.schools.models import Term
from apps.students.models import Student

from ..models import ReportCard, ReportCardBulkExport
from .report_card_pdf_service import render_report_card_pdf


def request_bulk_export(*, term: Term, class_arm=None, actor) -> ReportCardBulkExport:
    from ..tasks.reports import generate_report_cards_bulk_zip

    export = ReportCardBulkExport.objects.create(
        organization=term.organization,
        term=term,
        class_arm=class_arm,
        created_by=actor,
        updated_by=actor,
    )
    export_id, organization_id = export.id, export.organization_id
    transaction.on_commit(lambda: generate_report_cards_bulk_zip.delay(export_id, organization_id))
    return export


def run_bulk_export(*, export: ReportCardBulkExport) -> None:
    # Local import: report_card_service already imports tasks.reports (for
    # generate_report_card's own PDF enqueue) and tasks.reports needs this
    # module for the bulk task below — importing report_card_service at
    # module scope here would complete that cycle.
    from .report_card_service import generate_report_cards_bulk

    export.status = "processing"
    export.started_at = timezone.now()
    export.save(update_fields=["status", "started_at", "updated_at"])

    students = None
    if export.class_arm_id:
        students = Student.objects.filter(
            enrollments__academic_year=export.term.academic_year_id,
            enrollments__class_arm_id=export.class_arm_id,
        ).distinct()

    try:
        result = generate_report_cards_bulk(term=export.term, students=students, actor=export.created_by)
        report_cards = ReportCard.objects.filter(public_id__in=result["generated"])

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for report_card in report_cards:
                pdf_bytes = render_report_card_pdf(report_card)
                zip_file.writestr(f"{report_card.report_card_number}.pdf", pdf_bytes)

        file_url = save_file(
            key_prefix=f"report-card-bulk-exports/{export.organization_id}",
            filename=f"{export.term_id}-report-cards.zip",
            content=buffer.getvalue(),
            content_type="application/zip",
        )
    except Exception as exc:
        export.status = "failed"
        export.error_message = str(exc)[:255]
        export.save(update_fields=["status", "error_message", "updated_at"])
        return

    export.status = "ready"
    export.file_url = file_url
    export.report_card_count = len(result["generated"])
    export.failed_count = len(result["failed"])
    export.completed_at = timezone.now()
    export.save(
        update_fields=[
            "status",
            "file_url",
            "report_card_count",
            "failed_count",
            "completed_at",
            "updated_at",
        ]
    )
