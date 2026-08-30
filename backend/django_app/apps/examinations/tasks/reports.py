"""First real Celery task in the project (§18 exit criterion: "PDF report
cards via Celery"). Routed to the "reports" queue by config/celery.py's
task_routes glob (apps.*.tasks.reports.*). Runs synchronously in tests via
CELERY_TASK_ALWAYS_EAGER, so the PDF bytes and apps.core.storage fallback
are exercised for real rather than mocked.
"""
import io

from celery import shared_task
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from apps.core.storage import save_file
from apps.examinations.models import ReportCard, Result
from apps.tenancy.context import activate_organization


def _render_pdf(report_card: ReportCard) -> bytes:
    student = report_card.student
    results = (
        Result.objects.filter(
            student=student,
            assessment__term=report_card.term,
            status="published",
            deleted_at__isnull=True,
        )
        .select_related("assessment", "assessment__class_subject__subject")
        .order_by("assessment__class_subject__subject__name")
    )

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(40, height - 50, "Report Card")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(40, height - 75, f"Student: {student.first_name} {student.last_name}")
    pdf.drawString(40, height - 92, f"Term: {report_card.term.name}")

    y = height - 130
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(40, y, "Subject")
    pdf.drawString(280, y, "Score")
    pdf.drawString(360, y, "Grade")
    pdf.drawString(440, y, "Remark")
    pdf.setFont("Helvetica", 10)
    y -= 20
    for result in results:
        subject_name = result.assessment.class_subject.subject.name
        pdf.drawString(40, y, subject_name)
        pdf.drawString(280, y, str(result.score))
        pdf.drawString(360, y, result.grade)
        pdf.drawString(440, y, result.remark)
        y -= 18
        if y < 60:
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y = height - 60

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


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

    report_card.status = "generating"
    report_card.save(update_fields=["status", "updated_at"])

    try:
        pdf_bytes = _render_pdf(report_card)
        file_url = save_file(
            key_prefix=f"report-cards/{report_card.organization_id}",
            filename=f"{report_card.student_id}-{report_card.term_id}.pdf",
            content=pdf_bytes,
            content_type="application/pdf",
        )
    except Exception as exc:  # noqa: BLE001 - report the failure onto the row, don't crash the worker
        report_card.status = "failed"
        report_card.error_message = str(exc)[:255]
        report_card.save(update_fields=["status", "error_message", "updated_at"])
        return

    report_card.status = "ready"
    report_card.file_url = file_url
    report_card.generated_at = timezone.now()
    report_card.error_message = ""
    report_card.save(update_fields=["status", "file_url", "generated_at", "error_message", "updated_at"])
