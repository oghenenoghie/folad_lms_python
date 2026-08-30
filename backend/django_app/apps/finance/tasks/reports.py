"""Routed to the "reports" queue by config/celery.py's task_routes glob
(apps.*.tasks.reports.*), same as apps.examinations' report-card generation.
Enqueued via transaction.on_commit from payment_service.record_payment, so
this always runs after the payment itself has actually been committed.
"""
import io

from celery import shared_task
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from apps.core.storage import save_file
from apps.finance.models import Receipt
from apps.tenancy.context import activate_organization
from shared.money import Money


def _render_pdf(receipt: Receipt) -> bytes:
    payment = receipt.payment
    student = payment.invoice.student
    amount = Money(payment.amount_minor, payment.currency_code)

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(40, height - 50, "Payment Receipt")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(40, height - 75, f"Receipt number: {receipt.receipt_number}")
    pdf.drawString(40, height - 92, f"Student: {student.first_name} {student.last_name}")
    pdf.drawString(40, height - 109, f"Invoice: {payment.invoice.invoice_number}")
    pdf.drawString(40, height - 126, f"Amount paid: {amount}")
    pdf.drawString(40, height - 143, f"Method: {payment.get_method_display()}")
    pdf.drawString(40, height - 160, f"Reference: {payment.reference}")

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


@shared_task
def generate_receipt_pdf(receipt_id: int, organization_id: int) -> None:
    # A real (non-eager) worker gets a fresh DB connection with no
    # app.current_org GUC set, so without this the RLS-scoped
    # Receipt.objects lookup below always misses.
    activate_organization(organization_id)
    try:
        receipt = Receipt.objects.get(id=receipt_id)
    except Receipt.DoesNotExist:
        return

    receipt.status = "generating"
    receipt.save(update_fields=["status", "updated_at"])

    try:
        pdf_bytes = _render_pdf(receipt)
        file_url = save_file(
            key_prefix=f"receipts/{receipt.organization_id}",
            filename=f"{receipt.receipt_number}.pdf",
            content=pdf_bytes,
            content_type="application/pdf",
        )
    except Exception as exc:  # noqa: BLE001 - report the failure onto the row, don't crash the worker
        receipt.status = "failed"
        receipt.error_message = str(exc)[:255]
        receipt.save(update_fields=["status", "error_message", "updated_at"])
        return

    receipt.status = "ready"
    receipt.file_url = file_url
    receipt.generated_at = timezone.now()
    receipt.error_message = ""
    receipt.save(update_fields=["status", "file_url", "generated_at", "error_message", "updated_at"])
