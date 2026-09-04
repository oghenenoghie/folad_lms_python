import os
import sys
from pathlib import Path

# See the matching comment in manage.py: makes `import shared` (backend/shared/)
# resolve for a local (non-Docker) `celery -A config worker` too.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from celery import Celery  # noqa: E402
from celery.schedules import crontab  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("sms")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.task_routes = {
    "apps.*.tasks.reports.*": {"queue": "reports"},
    "apps.*.tasks.imports.*": {"queue": "imports"},
    "apps.*.tasks.notifications.*": {"queue": "email_notify"},
}

# Requires a `celery -A config beat` process running alongside the worker
# (see RAILWAY_DEPLOYMENT.md) — the worker alone never fires scheduled
# tasks on its own.
app.conf.beat_schedule = {
    "send-fee-reminders-daily": {
        "task": "apps.finance.tasks.notifications.send_fee_reminders",
        "schedule": crontab(hour=7, minute=0),
    },
}
