"""Routed to the "reports" queue by config/celery.py's task_routes glob
(apps.*.tasks.reports.*) — same convention apps.examinations' old
ReportCard task and apps.finance's Receipt task already established.
Runs synchronously in tests via CELERY_TASK_ALWAYS_EAGER.
"""
from celery import shared_task
from django.utils import timezone

from apps.core.storage import save_file
from apps.tenancy.context import activate_organization

from ..models import ReportCard, ReportCardBulkExport
from ..services.report_card_pdf_service import render_report_card_pdf


@shared_task
def generate_report_card_pdf(report_card_id: int, organization_id: int) -> None:
    # A real (non-eager) worker gets a fresh DB connection with no
    # app.current_org GUC set, so without this the RLS-scoped
    # ReportCard.objects lookup below always misses.
    activate_organization(organization_id)
    try:
        report_card = ReportCard.objects.get(id=report_card_id)
    except ReportCard.DoesNotExist:
        return

    report_card.pdf_status = "generating"
    report_card.save(update_fields=["pdf_status", "updated_at"])

    try:
        pdf_bytes = render_report_card_pdf(report_card)
        file_url = save_file(
            key_prefix=f"report-cards/{report_card.organization_id}",
            filename=f"{report_card.report_card_number}.pdf",
            content=pdf_bytes,
            content_type="application/pdf",
        )
    except Exception as exc:  # noqa: BLE001 - report the failure onto the row, don't crash the worker
        report_card.pdf_status = "failed"
        report_card.pdf_error_message = str(exc)[:255]
        report_card.save(update_fields=["pdf_status", "pdf_error_message", "updated_at"])
        return

    report_card.pdf_status = "ready"
    report_card.pdf_file_url = file_url
    report_card.pdf_generated_at = timezone.now()
    report_card.pdf_error_message = ""
    report_card.save(
        update_fields=["pdf_status", "pdf_file_url", "pdf_generated_at", "pdf_error_message", "updated_at"]
    )


@shared_task
def generate_report_cards_bulk_zip(export_id: int, organization_id: int) -> None:
    activate_organization(organization_id)
    try:
        export = ReportCardBulkExport.objects.get(id=export_id)
    except ReportCardBulkExport.DoesNotExist:
        return

    # Local import: report_card_bulk_export_service needs report_card_
    # service (imported at module scope there) which itself imports this
    # module at module scope — importing run_bulk_export at module scope
    # here would complete that cycle.
    from ..services.report_card_bulk_export_service import run_bulk_export

    run_bulk_export(export=export)
