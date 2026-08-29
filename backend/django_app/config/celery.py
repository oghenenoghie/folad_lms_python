import os
import sys
from pathlib import Path

# See the matching comment in manage.py: makes `import shared` (backend/shared/)
# resolve for a local (non-Docker) `celery -A config worker` too.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from celery import Celery  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("sms")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.task_routes = {
    "apps.*.tasks.reports.*": {"queue": "reports"},
    "apps.*.tasks.imports.*": {"queue": "imports"},
    "apps.*.tasks.notifications.*": {"queue": "email_notify"},
}
