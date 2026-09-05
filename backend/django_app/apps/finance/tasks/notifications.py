"""Routed to the "email_notify" queue by config/celery.py's task_routes
glob (apps.*.tasks.notifications.*) and scheduled daily via
config/celery.py's beat_schedule — a Celery Beat process must be running
alongside the worker for this to actually fire (see RAILWAY_DEPLOYMENT.md).
"""
from celery import shared_task

from apps.finance.services import reminder_service
from apps.tenancy.context import activate_organization
from apps.tenancy.models import Organization


@shared_task
def send_fee_reminders() -> int:
    """Sends fee-due/overdue reminder notifications across every active
    organization. Returns the total number of invoices reminded."""
    total = 0
    for organization_id in Organization.objects.filter(is_active=True).values_list("id", flat=True):
        # A real (non-eager) worker gets a fresh DB connection with no
        # app.current_org GUC set, so without this the RLS-scoped
        # Invoice.objects lookups in reminder_service always miss — same
        # requirement as apps.finance.tasks.reports.generate_receipt_pdf.
        activate_organization(organization_id)
        total += reminder_service.send_reminders_for_organization(organization_id=organization_id)
    return total
