"""Automated fee-due/overdue reminder notifications. Driven daily by
apps.finance.tasks.notifications.send_fee_reminders (Celery Beat) — see
that module for the schedule. Kept in its own service so the query/
notification logic is directly unit-testable without going through
Celery or the RLS-scoping dance the task wrapper needs.
"""
from datetime import timedelta

from django.utils import timezone

from apps.communication.models import Notification
from apps.finance.models import Invoice
from apps.finance.services.invoice_service import amount_paid_net_minor
from apps.parents.models import GuardianStudent
from shared.money import Money

# An invoice due within this many days (or already overdue) is reminder-
# eligible; REMINDER_COOLDOWN_DAYS then keeps the daily task from
# re-notifying the same invoice every single day it stays eligible.
UPCOMING_REMINDER_DAYS = 3
REMINDER_COOLDOWN_DAYS = 7


def _recipient_user_ids(invoice: Invoice) -> set[int]:
    """The student's own user (if linked) plus every guardian linked to
    that student — whoever might actually be the one paying."""
    recipients = set()
    if invoice.student.user_id:
        recipients.add(invoice.student.user_id)
    recipients.update(
        uid
        for uid in GuardianStudent.objects.filter(
            student=invoice.student, deleted_at__isnull=True
        ).values_list("guardian__user_id", flat=True)
        if uid
    )
    return recipients


def _notify_for_invoice(*, invoice: Invoice, outstanding_minor: int, today) -> int:
    amount = Money(outstanding_minor, invoice.currency_code)
    is_overdue = invoice.due_date < today
    title = "Fee payment overdue" if is_overdue else "Fee payment due soon"
    body = (
        f"Invoice {invoice.invoice_number} for {invoice.student} has {amount} outstanding, "
        f"{'overdue since' if is_overdue else 'due'} {invoice.due_date}."
    )
    # /my-fees/<id> is a student-only page (see MyInvoiceDetailPage's
    # student_public_id check) — guardians have no fee-detail page of
    # their own yet, so a guardian's notification carries no deep link
    # rather than one that would 403/error for them.
    student_user_id = invoice.student.user_id
    sent = 0
    for user_id in _recipient_user_ids(invoice):
        Notification.objects.create(
            organization_id=invoice.organization_id,
            recipient_id=user_id,
            notification_type="fee_reminder",
            title=title,
            body=body,
            link_url=f"/my-fees/{invoice.public_id}" if user_id == student_user_id else "",
            ref_type="invoice",
            ref_id=invoice.id,
        )
        sent += 1
    return sent


def send_reminders_for_organization(*, organization_id: int) -> int:
    """Sends a fee reminder for every invoice in this organization that's
    due within UPCOMING_REMINDER_DAYS or already overdue, skipping any
    invoice reminded within the last REMINDER_COOLDOWN_DAYS or already
    fully paid. Returns the number of invoices reminded (not the number
    of notifications sent — one invoice can have several recipients, or
    none if the student has no linked user and no guardians).
    """
    today = timezone.localdate()
    cutoff = today + timedelta(days=UPCOMING_REMINDER_DAYS)
    cooldown_start = timezone.now() - timedelta(days=REMINDER_COOLDOWN_DAYS)

    candidates = (
        Invoice.objects.filter(
            organization_id=organization_id,
            status__in=["issued", "partially_paid"],
            due_date__isnull=False,
            due_date__lte=cutoff,
        )
        .exclude(reminder_sent_at__gte=cooldown_start)
        .select_related("student")
    )

    reminded = 0
    for invoice in candidates:
        outstanding = invoice.total_minor - amount_paid_net_minor(invoice)
        if outstanding <= 0:
            continue
        if _notify_for_invoice(invoice=invoice, outstanding_minor=outstanding, today=today) == 0:
            continue
        invoice.reminder_sent_at = timezone.now()
        invoice.save(update_fields=["reminder_sent_at", "updated_at"])
        reminded += 1
    return reminded
