"""Thin views, fat services (§11 ARCHITECTURE.md). §18's "refunds as
reversals" exit criterion: a Refund never edits the original Payment or its
ledger entries — it's a new row whose ledger post is the exact mirror of the
payment's (debit/credit swapped), and the parent Invoice's status is
recomputed from the net (paid - refunded) balance, same helper the payment
side uses.
"""
from django.db import transaction
from django.utils import timezone

from apps.finance.models import Payment, Refund
from apps.finance.services import invoice_service, ledger_service
from apps.finance.services.exceptions import InvalidRefundAmount


def issue_refund(*, payment: Payment, actor, amount_minor: int, reason: str = "") -> Refund:
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if payment.status != "successful":
            raise InvalidRefundAmount(f"cannot refund a payment that is '{payment.status}'")
        if amount_minor <= 0:
            raise InvalidRefundAmount("amount_minor must be positive")
        already_refunded = sum(
            r.amount_minor for r in payment.refunds.filter(status="completed", deleted_at__isnull=True)
        )
        refundable = payment.amount_minor - already_refunded
        if amount_minor > refundable:
            raise InvalidRefundAmount(
                f"amount_minor ({amount_minor}) exceeds the refundable balance ({refundable})"
            )

        refund = Refund.objects.create(
            organization=payment.organization,
            school=payment.school,
            payment=payment,
            amount_minor=amount_minor,
            currency_code=payment.currency_code,
            reason=reason,
            processed_at=timezone.now(),
            created_by=actor,
            updated_by=actor,
        )
        # Mirror image of the payment's own post (debit/credit swapped).
        ledger_service.post_double_entry(
            organization=payment.organization,
            school=payment.school,
            currency_code=payment.currency_code,
            debit_account=ledger_service.ACCOUNT_ACCOUNTS_RECEIVABLE,
            credit_account=ledger_service.ACCOUNT_CASH,
            amount_minor=amount_minor,
            ref_type="refund",
            ref_id=refund.id,
            description=f"Refund against payment {payment.reference}",
            actor=actor,
        )

        invoice = payment.invoice
        paid_net = invoice_service.amount_paid_net_minor(invoice)
        if paid_net <= 0:
            invoice.status = "issued"
        elif paid_net < invoice.total_minor:
            invoice.status = "partially_paid"
        else:
            invoice.status = "paid"
        invoice.updated_by = actor
        invoice.save(update_fields=["status", "updated_by", "updated_at"])
    return refund
