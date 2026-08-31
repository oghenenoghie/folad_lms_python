"""Unfold's UNFOLD["DASHBOARD_CALLBACK"] hook (see config/settings/base.py).
Renders the stat cards / charts / recent-activity widgets on the admin index
page (templates/admin/index.html). Only ever runs for staff-authenticated
/admin/ requests, so it queries with `all_tenants` (cross-organization) the
same way AdminPlatformModeMiddleware already grants the request DB-level
visibility for — a per-tenant admin would otherwise see an empty dashboard.

Every number here comes from a real query — no placeholder/fabricated
metric. A few widgets from common "admin dashboard" templates (an
admissions CRM funnel, AI-generated insights, task/priority tracking,
per-staff productivity scoring, an events calendar) are deliberately not
here: none of that data exists anywhere in this schema, and inventing
plausible-looking numbers for them would be worse than not showing them.
"""
import json
from datetime import timedelta

from django.db.models import Count, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth
from django.http import HttpRequest
from django.utils import timezone

from apps.accounts.models import LoginHistory
from apps.attendance.models import Attendance
from apps.finance.models import Invoice, Payment
from apps.staff.models import Staff
from apps.students.models import Student
from apps.tenancy.models import Organization


def _today_collection_minor() -> int:
    today = timezone.localdate()
    total = Payment.all_tenants.filter(status="successful", paid_at__date=today).aggregate(
        total=Coalesce(Sum("amount_minor"), Value(0))
    )
    return total["total"]


def _total_receivables_minor() -> int:
    # Outstanding = billed minus collected, across every invoice that's
    # still owed anything — the same shape as dashboard_service's own
    # per-guardian outstanding-fees calculation, just aggregated in the DB
    # instead of looped in Python (this one runs over every student in the
    # org, not a guardian's handful of children).
    invoices = Invoice.all_tenants.filter(status__in=["issued", "partially_paid"]).annotate(
        paid_minor=Coalesce(
            Sum("payments__amount_minor", filter=Q(payments__status="successful")), Value(0)
        )
    )
    return sum(max(invoice.total_minor - invoice.paid_minor, 0) for invoice in invoices)


def _attendance_today_pct() -> float | None:
    today = timezone.localdate()
    counts = Attendance.all_tenants.filter(date=today).aggregate(
        total=Count("id"), present=Count("id", filter=Q(status="present"))
    )
    if not counts["total"]:
        return None
    return round(counts["present"] * 100 / counts["total"], 1)


def _new_admissions_this_month() -> int:
    start_of_month = timezone.localdate().replace(day=1)
    return Student.all_tenants.filter(created_at__date__gte=start_of_month).count()


def _revenue_chart_json(days: int = 30) -> str:
    start_date = timezone.localdate() - timedelta(days=days - 1)
    rows = (
        Payment.all_tenants.filter(status="successful", paid_at__date__gte=start_date)
        .values("paid_at__date")
        .annotate(total=Sum("amount_minor"))
    )
    totals_by_date = {row["paid_at__date"]: row["total"] for row in rows}

    labels, values = [], []
    cursor = start_date
    today = timezone.localdate()
    while cursor <= today:
        labels.append(cursor.strftime("%d %b"))
        values.append((totals_by_date.get(cursor) or 0) / 100)
        cursor += timedelta(days=1)

    return json.dumps(
        {
            "labels": labels,
            "datasets": [
                {
                    "label": "Collected",
                    "data": values,
                    "backgroundColor": "var(--color-primary-600)",
                    "borderRadius": 4,
                }
            ],
        }
    )


def _attendance_heatmap(days: int = 7) -> dict:
    start_date = timezone.localdate() - timedelta(days=days - 1)
    today = timezone.localdate()
    dates = []
    cursor = start_date
    while cursor <= today:
        dates.append(cursor)
        cursor += timedelta(days=1)

    rows = (
        Attendance.all_tenants.filter(date__gte=start_date, date__lte=today)
        .values("date", "enrollment__class_arm__class_level__name")
        .annotate(total=Count("id"), present=Count("id", filter=Q(status="present")))
    )

    by_class: dict[str, dict] = {}
    for row in rows:
        class_name = row["enrollment__class_arm__class_level__name"]
        if class_name is None:
            continue
        by_class.setdefault(class_name, {})[row["date"]] = (
            round(row["present"] * 100 / row["total"]) if row["total"] else None
        )

    return {
        "dates": dates,
        "classes": [
            {"name": name, "values": [values.get(d) for d in dates]}
            for name, values in sorted(by_class.items())
        ],
    }


def _top_defaulters(limit: int = 5) -> list[dict]:
    today = timezone.localdate()
    overdue_invoices = (
        Invoice.all_tenants.filter(status__in=["issued", "partially_paid"], due_date__lt=today)
        .annotate(
            paid_minor=Coalesce(
                Sum("payments__amount_minor", filter=Q(payments__status="successful")), Value(0)
            )
        )
        .select_related("student")
    )

    # One overdue student can have several overdue invoices — combine them
    # into a single ranked row rather than listing the same student
    # multiple times. The org-wide set of currently-overdue invoices is
    # small by nature (a school's live delinquency list, not its full
    # billing history), so this Python-side merge stays cheap.
    by_student: dict[int, dict] = {}
    for invoice in overdue_invoices:
        outstanding = invoice.total_minor - invoice.paid_minor
        if outstanding <= 0:
            continue
        days_overdue = (today - invoice.due_date).days
        entry = by_student.setdefault(
            invoice.student_id, {"student": invoice.student, "outstanding_minor": 0, "days_overdue": 0}
        )
        entry["outstanding_minor"] += outstanding
        entry["days_overdue"] = max(entry["days_overdue"], days_overdue)

    return sorted(by_student.values(), key=lambda entry: -entry["outstanding_minor"])[:limit]


def dashboard_callback(request: HttpRequest, context: dict) -> dict:
    attendance_pct = _attendance_today_pct()

    context["stat_cards"] = [
        {"title": "Organizations", "value": Organization.objects.filter(is_active=True).count(), "icon": "corporate_fare"},
        {"title": "Active students", "value": Student.all_tenants.filter(enrollment_status="active").count(), "icon": "groups"},
        {"title": "Active staff", "value": Staff.all_tenants.filter(employment_status="active").count(), "icon": "badge"},
        {"title": "New admissions (this month)", "value": _new_admissions_this_month(), "icon": "person_add"},
        {"title": "Today's collection", "value": f"{_today_collection_minor() / 100:,.2f}", "icon": "payments"},
        {
            "title": "Attendance today",
            "value": f"{attendance_pct}%" if attendance_pct is not None else "—",
            "icon": "fact_check",
        },
    ]
    context["total_receivables_subtitle"] = f"Total receivables: {_total_receivables_minor() / 100:,.2f}"

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
    context["attendance_heatmap"] = _attendance_heatmap()
    context["top_defaulters"] = _top_defaulters()

    context["recent_logins"] = list(
        LoginHistory.all_tenants.select_related("user", "organization")
        .order_by("-created_at")[:8]
    )

    return context
