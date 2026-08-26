"""Unfold's UNFOLD["DASHBOARD_CALLBACK"] hook (see config/settings/base.py).
Renders the stat cards / chart / recent-activity widgets on the admin index
page (templates/admin/index.html). Only ever runs for staff-authenticated
/admin/ requests, so it queries with `all_tenants` (cross-organization) the
same way AdminPlatformModeMiddleware already grants the request DB-level
visibility for — a per-tenant admin would otherwise see an empty dashboard.
"""
import json
from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.http import HttpRequest
from django.utils import timezone

from apps.accounts.models import LoginHistory
from apps.parents.models import Guardian
from apps.schools.models import School
from apps.staff.models import Staff
from apps.students.models import Student
from apps.tenancy.models import Organization


def dashboard_callback(request: HttpRequest, context: dict) -> dict:
    context["stat_cards"] = [
        {
            "title": "Organizations",
            "value": Organization.objects.filter(is_active=True).count(),
            "icon": "corporate_fare",
        },
        {
            "title": "Schools",
            "value": School.all_tenants.count(),
            "icon": "school",
        },
        {
            "title": "Students",
            "value": Student.all_tenants.filter(enrollment_status="active").count(),
            "icon": "groups",
        },
        {
            "title": "Staff",
            "value": Staff.all_tenants.filter(employment_status="active").count(),
            "icon": "badge",
        },
        {
            "title": "Guardians",
            "value": Guardian.all_tenants.count(),
            "icon": "family_restroom",
        },
    ]

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

    context["recent_logins"] = list(
        LoginHistory.all_tenants.select_related("user", "organization")
        .order_by("-created_at")[:8]
    )

    return context
