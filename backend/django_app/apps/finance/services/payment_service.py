"""Thin views, fat services (§11 ARCHITECTURE.md). Transactional payment
posting (§18 exit criterion): select_for_update() on the parent Invoice
serializes concurrent payments against the same invoice so two racing
requests can never both post against the same outstanding balance and
together overpay it; `reference`'s uniqueness constraint (see models.py)
makes a retried post with the same idempotency key a clean 409 rather than
a double-post. Receipt PDF generation is enqueued via transaction.on_commit
so a slow/failed Celery broker can never roll back money that has already
moved — same reasoning as apps.examinations' report-card generation, but
here it matters more since this is inside a financial transaction.
"""
from django.db import transaction
from django.utils import timezone

from apps.finance.models import Invoice, Payment
from apps.finance.services import invoice_service, ledger_service, receipt_service
from apps.finance.services.exceptions import InvalidPaymentAmount
from apps.finance.tasks.reports import generate_receipt_pdf


def record_payment(
    *, invoice: Invoice, actor, reference: str, amount_minor: int, method: str, paid_at=None, **fields
) -> Payment:
    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
        if invoice.status not in ("issued", "partially_paid"):
            raise InvalidPaymentAmount(
                f"cannot record a payment against an invoice that is '{invoice.status}'"
            )
        if amount_minor <= 0:
            raise InvalidPaymentAmount("amount_minor must be positive")
        outstanding = invoice.total_minor - invoice_service.amount_paid_net_minor(invoice)
        if amount_minor > outstanding:
            raise InvalidPaymentAmount(
                f"amount_minor ({amount_minor}) exceeds the outstanding balance ({outstanding})"
            )

        payment = Payment.objects.create(
            organization=invoice.organization,
            school=invoice.school,
            invoice=invoice,
            reference=reference,
            amount_minor=amount_minor,
            currency_code=invoice.currency_code,
            method=method,
            paid_at=paid_at or timezone.now(),
            created_by=actor,
            updated_by=actor,
            **fields,
        )
        ledger_service.post_double_entry(
            organization=invoice.organization,
            school=invoice.school,
            currency_code=invoice.currency_code,
            debit_account=ledger_service.ACCOUNT_CASH,
            credit_account=ledger_service.ACCOUNT_ACCOUNTS_RECEIVABLE,
            amount_minor=amount_minor,
            ref_type="payment",
            ref_id=payment.id,
            description=f"Payment {reference} against invoice {invoice.invoice_number}",
            actor=actor,
        )

        invoice.status = "paid" if amount_minor >= outstanding else "partially_paid"
        invoice.updated_by = actor
        invoice.save(update_fields=["status", "updated_by", "updated_at"])

        receipt = receipt_service.create_receipt(payment=payment, actor=actor)
        transaction.on_commit(lambda: generate_receipt_pdf.delay(receipt.id, receipt.organization_id))
    return payment
