"""Thin views, fat services (§11 ARCHITECTURE.md). Receipt is always created
as a side effect of payment_service.record_payment, never directly by a
client — receipt_number is derived from the payment's own (already-unique)
reference rather than being another caller-supplied identifier.
"""
from apps.finance.models import Payment, Receipt


def create_receipt(*, payment: Payment, actor) -> Receipt:
    return Receipt.objects.create(
        organization=payment.organization,
        school=payment.school,
        payment=payment,
        receipt_number=f"RCPT-{payment.reference}",
        created_by=actor,
        updated_by=actor,
    )
