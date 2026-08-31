"""Unfold's UNFOLD["DASHBOARD_CALLBACK"] hook (see config/settings/base.py).
Renders the stat cards / charts / recent-activity widgets on the admin index
page (templates/admin/index.html). Only ever runs for staff-authenticated
/admin/ requests, so it queries with `all_tenants` (cross-organization) the
same way AdminPlatformModeMiddleware already grants the request DB-level
visibility for — a per-tenant admin would otherwise see an empty dashboard.

The actual aggregate math lives in apps.core.dashboard_metrics, shared with
the JSON API's admin dashboard summary (apps/dashboards/services/
dashboard_service.py) — this module only supplies the `all_tenants`
querysets and turns the results into template/Chart.js-shaped context.

Every number here comes from a real query — no placeholder/fabricated
metric. A few widgets from common "admin dashboard" templates (an
admissions CRM funnel, AI-generated insights, task/priority tracking,
per-staff productivity scoring, an events calendar) are deliberately not
here: none of that data exists anywhere in this schema, and inventing
plausible-looking numbers for them would be worse than not showing them.
"""
import json
from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.http import HttpRequest
from django.utils import timezone

from apps.accounts.models import LoginHistory
from apps.attendance.models import Attendance
from apps.core import dashboard_metrics as metrics
from apps.finance.models import Invoice, Payment
from apps.staff.models import Staff
from apps.students.models import Student
from apps.tenancy.models import Organization


def _revenue_chart_json(days: int = 30) -> str:
    series = metrics.revenue_series(Payment.all_tenants, days=days)
    return json.dumps(
        {
            "labels": [row["date"].strftime("%d %b") for row in series],
            "datasets": [
                {
                    "label": "Collected",
                    "data": [row["amount_minor"] / 100 for row in series],
                    "backgroundColor": "var(--color-primary-600)",
                    "borderRadius": 4,
                }
            ],
        }
    )


def dashboard_callback(request: HttpRequest, context: dict) -> dict:
    attendance_pct = metrics.attendance_today_pct(Attendance.all_tenants)

    context["stat_cards"] = [
        {"title": "Organizations", "value": Organization.objects.filter(is_active=True).count(), "icon": "corporate_fare"},
        {"title": "Active students", "value": Student.all_tenants.filter(enrollment_status="active").count(), "icon": "groups"},
        {"title": "Active staff", "value": Staff.all_tenants.filter(employment_status="active").count(), "icon": "badge"},
        {"title": "New admissions (this month)", "value": metrics.new_admissions_this_month(Student.all_tenants), "icon": "person_add"},
        {"title": "Today's collection", "value": f"{metrics.today_collection_minor(Payment.all_tenants) / 100:,.2f}", "icon": "payments"},
        {
            "title": "Attendance today",
            "value": f"{attendance_pct}%" if attendance_pct is not None else "—",
            "icon": "fact_check",
        },
    ]
    context["total_receivables_subtitle"] = (
        f"Total receivables: {metrics.total_receivables_minor(Invoice.all_tenants) / 100:,.2f}"
    )

    six_months_ago = (timezone.now() - timedelta(days=180)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    enrollments_by_month = (
        Student.all_tenants.filter(created_at__gte=six_months_ago)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    months_lookup = {row["month"].strftime("%Y-%m"): row["count"] for row in enrollments_by_month}
    chart_labels = []
    chart_values = []
    cursor = six_months_ago
    now = timezone.now()
    while cursor <= now:
        key = cursor.strftime("%Y-%m")
        chart_labels.append(cursor.strftime("%b"))
        chart_values.append(months_lookup.get(key, 0))
        cursor = (cursor + timedelta(days=32)).replace(day=1)

    context["enrollment_chart_json"] = json.dumps(
        {
            "labels": chart_labels,
            "datasets": [
                {
                    "label": "New students",
                    "data": chart_values,
                    "backgroundColor": "var(--color-primary-600)",
                    "borderRadius": 4,
                }
            ],
        }
    )

    context["revenue_chart_json"] = _revenue_chart_json()
    context["attendance_heatmap"] = metrics.attendance_heatmap(Attendance.all_tenants)
    context["top_defaulters"] = metrics.top_defaulters(Invoice.all_tenants)

    context["recent_logins"] = list(
        LoginHistory.all_tenants.select_related("user", "organization")
        .order_by("-created_at")[:8]
    )

    return context
