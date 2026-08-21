import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("sms")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.task_routes = {
    "apps.*.tasks.reports.*": {"queue": "reports"},
    "apps.*.tasks.imports.*": {"queue": "imports"},
    "apps.*.tasks.notifications.*": {"queue": "email_notify"},
}
