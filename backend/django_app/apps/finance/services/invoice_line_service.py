"""Thin views, fat services (§11 ARCHITECTURE.md). Lines are mutable only
while the parent Invoice is still "draft" (see invoice_service.issue_invoice) —
each mutation recomputes both the line's own amount_minor and the invoice's
total_minor so the two can never drift apart.
"""
from django.db import transaction
from django.utils import timezone

from apps.finance.models import Discount, FeeItem, Invoice, InvoiceLine
from apps.finance.services import discount_service
from apps.finance.services.exceptions import InvalidInvoiceState


def _require_draft(invoice: Invoice) -> None:
    if invoice.status != "draft":
        raise InvalidInvoiceState(f"cannot modify lines once the invoice is '{invoice.status}'")


def _recompute_invoice_total(invoice: Invoice, actor) -> None:
    total = sum(
        line.amount_minor for line in invoice.lines.filter(deleted_at__isnull=True)
    )
    invoice.total_minor = total
    invoice.updated_by = actor
    invoice.save(update_fields=["total_minor", "updated_by", "updated_at"])


def add_line(
    *, invoice: Invoice, actor, fee_item: FeeItem | None = None, discount: Discount | None = None,
    description: str | None = None, quantity: int = 1, unit_amount_minor: int | None = None,
) -> InvoiceLine:
    _require_draft(invoice)
    if unit_amount_minor is None:
        if fee_item is None:
            raise InvalidInvoiceState("a line needs either a fee_item or an explicit unit_amount_minor")
        unit_amount_minor = fee_item.amount_minor
    if description is None:
        description = fee_item.name if fee_item else "Charge"
    base_amount = quantity * unit_amount_minor
    discount_amount = discount_service.compute_discount_amount_minor(
        discount=discount, base_amount_minor=base_amount
    )
    with transaction.atomic():
        line = InvoiceLine.objects.create(
            organization=invoice.organization,
            invoice=invoice,
            fee_item=fee_item,
            description=description,
            quantity=quantity,
            unit_amount_minor=unit_amount_minor,
            discount=discount,
            discount_amount_minor=discount_amount,
            amount_minor=base_amount - discount_amount,
            created_by=actor,
            updated_by=actor,
        )
        _recompute_invoice_total(invoice, actor)
    return line


def update_line(*, line: InvoiceLine, actor, **fields) -> InvoiceLine:
    invoice = line.invoice
    _require_draft(invoice)
    for field, value in fields.items():
        setattr(line, field, value)
    base_amount = line.quantity * line.unit_amount_minor
    line.discount_amount_minor = discount_service.compute_discount_amount_minor(
        discount=line.discount, base_amount_minor=base_amount
    )
    line.amount_minor = base_amount - line.discount_amount_minor
    line.updated_by = actor
    with transaction.atomic():
        line.save(
            update_fields=[
                *fields.keys(), "discount_amount_minor", "amount_minor", "updated_by", "updated_at",
            ]
        )
        _recompute_invoice_total(invoice, actor)
    return line


def remove_line(*, line: InvoiceLine, actor) -> None:
    invoice = line.invoice
    _require_draft(invoice)
    with transaction.atomic():
        line.deleted_at = timezone.now()
        line.updated_by = actor
        line.save(update_fields=["deleted_at", "updated_by", "updated_at"])
        _recompute_invoice_total(invoice, actor)
