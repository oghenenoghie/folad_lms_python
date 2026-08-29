"""Thin views, fat services (§11 ARCHITECTURE.md). Invoice lines may only be
added/edited/removed while status="draft" (see invoice_line_service) — once
issued, an invoice's total is what was actually posted to the ledger and
must not silently drift. issue_invoice()/cancel_invoice() are the only two
status transitions here; record_payment (payment_service) drives the rest
(partially_paid/paid) as money actually arrives.
"""
from django.db import transaction
from django.utils import timezone

from apps.finance.models import Invoice, Refund
from apps.finance.services import ledger_service
from apps.finance.services.exceptions import InvalidInvoiceState
from apps.schools.models import Term
from apps.students.models import Student


def create_invoice(*, student: Student, term: Term, actor, **fields) -> Invoice:
    return Invoice.objects.create(
        organization=term.organization,
        school=term.academic_year.school,
        student=student,
        academic_year=term.academic_year,
        term=term,
        currency_code=term.organization.currency_code,
        created_by=actor,
        updated_by=actor,
        **fields,
    )


def update_invoice(*, invoice: Invoice, actor, **fields) -> Invoice:
    if invoice.status != "draft":
        raise InvalidInvoiceState(f"cannot edit an invoice once it is '{invoice.status}'")
    for field, value in fields.items():
        setattr(invoice, field, value)
    invoice.updated_by = actor
    invoice.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return invoice


def delete_invoice(*, invoice: Invoice, actor) -> None:
    if invoice.status != "draft":
        raise InvalidInvoiceState(f"cannot delete an invoice once it is '{invoice.status}'")
    invoice.deleted_at = timezone.now()
    invoice.updated_by = actor
    invoice.save(update_fields=["deleted_at", "updated_by", "updated_at"])


def amount_paid_net_minor(invoice: Invoice) -> int:
    """Successful payments minus completed refunds against those payments."""
    paid = sum(
        p.amount_minor for p in invoice.payments.filter(status="successful", deleted_at__isnull=True)
    )
    refunded = sum(
        r.amount_minor
        for r in Refund.objects.filter(
            payment__invoice=invoice, status="completed", deleted_at__isnull=True
        )
    )
    return paid - refunded


def issue_invoice(*, invoice: Invoice, actor) -> Invoice:
    if invoice.status != "draft":
        raise InvalidInvoiceState(f"cannot issue an invoice that is already '{invoice.status}'")
    if invoice.total_minor <= 0:
        raise InvalidInvoiceState("cannot issue an invoice with no lines")
    with transaction.atomic():
        ledger_service.post_double_entry(
            organization=invoice.organization,
            school=invoice.school,
            currency_code=invoice.currency_code,
            debit_account=ledger_service.ACCOUNT_ACCOUNTS_RECEIVABLE,
            credit_account=ledger_service.ACCOUNT_REVENUE,
            amount_minor=invoice.total_minor,
            ref_type="invoice",
            ref_id=invoice.id,
            description=f"Invoice {invoice.invoice_number} issued",
            actor=actor,
        )
        invoice.status = "issued"
        invoice.issued_at = timezone.now()
        invoice.updated_by = actor
        invoice.save(update_fields=["status", "issued_at", "updated_by", "updated_at"])
    return invoice


def cancel_invoice(*, invoice: Invoice, actor) -> Invoice:
    if invoice.status not in ("draft", "issued"):
        raise InvalidInvoiceState(
            f"cannot cancel an invoice once payments exist against it (current status: {invoice.status})"
        )
    with transaction.atomic():
        if invoice.status == "issued":
            ledger_service.post_double_entry(
                organization=invoice.organization,
                school=invoice.school,
                currency_code=invoice.currency_code,
                debit_account=ledger_service.ACCOUNT_REVENUE,
                credit_account=ledger_service.ACCOUNT_ACCOUNTS_RECEIVABLE,
                amount_minor=invoice.total_minor,
                ref_type="invoice",
                ref_id=invoice.id,
                description=f"Invoice {invoice.invoice_number} cancelled",
                actor=actor,
            )
        invoice.status = "cancelled"
        invoice.updated_by = actor
        invoice.save(update_fields=["status", "updated_by", "updated_at"])
    return invoice
