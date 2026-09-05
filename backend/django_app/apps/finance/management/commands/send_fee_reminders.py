"""Manual/cron-triggerable entry point for the same logic as
apps.finance.tasks.notifications.send_fee_reminders. Exists because
Celery Beat isn't deployed on Railway yet (see RAILWAY_DEPLOYMENT.md's
"not-yet-built" note) — until it is, this command is how the daily
reminder actually runs, e.g. from Railway's own cron/scheduled-job
feature or a one-off manual run, rather than relying on a Celery Beat
process this deployment doesn't have.
"""
from django.core.management.base import BaseCommand

from apps.finance.tasks.notifications import send_fee_reminders


class Command(BaseCommand):
    help = "Sends fee-due/overdue reminder notifications across every active organization."

    def handle(self, *args, **options):
        # .run() executes the task function directly and synchronously,
        # in-process — no worker/broker involved, unlike .delay()/.apply_async().
        count = send_fee_reminders.run()
        self.stdout.write(self.style.SUCCESS(f"Reminded {count} invoice(s)."))
