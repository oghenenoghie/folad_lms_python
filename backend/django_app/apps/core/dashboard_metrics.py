"""Pure aggregate-metric calculations shared by every admin-facing
dashboard. Each function takes a base queryset rather than a model
manager, so the caller controls tenant scope: the Django Admin dashboard
(apps/core/dashboard.py) passes `all_tenants` querysets under
platform-mode (cross-organization), while the JSON API's admin summary
(apps/dashboards/services/dashboard_service.py) passes the normal
tenant-scoped `objects` manager (single organization, via RLS/TenantManager).
No organization/tenant concept lives here — that's entirely the caller's
job — which is what lets both call sites share one implementation.
"""
from datetime import date, timedelta

from django.db.models import Count, Q, QuerySet, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone


def today_collection_minor(payment_qs: QuerySet) -> int:
    today = timezone.localdate()
    total = payment_qs.filter(status="successful", paid_at__date=today).aggregate(
        total=Coalesce(Sum("amount_minor"), Value(0))
    )
    return total["total"]


def total_receivables_minor(invoice_qs: QuerySet) -> int:
    # Outstanding = billed minus collected, across every invoice that's
    # still owed anything.
    invoices = invoice_qs.filter(status__in=["issued", "partially_paid"]).annotate(
        paid_minor=Coalesce(
            Sum("payments__amount_minor", filter=Q(payments__status="successful")), Value(0)
        )
    )
    return sum(max(invoice.total_minor - invoice.paid_minor, 0) for invoice in invoices)


def attendance_today_pct(attendance_qs: QuerySet) -> float | None:
    today = timezone.localdate()
    counts = attendance_qs.filter(date=today).aggregate(
        total=Count("id"), present=Count("id", filter=Q(status="present"))
    )
    if not counts["total"]:
        return None
    return round(counts["present"] * 100 / counts["total"], 1)


def new_admissions_this_month(student_qs: QuerySet) -> int:
    start_of_month = timezone.localdate().replace(day=1)
    return student_qs.filter(created_at__date__gte=start_of_month).count()


def revenue_series(payment_qs: QuerySet, days: int = 30) -> list[dict]:
    """One entry per day for the trailing `days` days (including today),
    zero-filled where nothing was collected — a caller-agnostic shape
    (Django template turns it into Chart.js JSON; the API returns it as-is
    and lets DRF's encoder serialize the `date` objects)."""
    start_date = timezone.localdate() - timedelta(days=days - 1)
    rows = (
        payment_qs.filter(status="successful", paid_at__date__gte=start_date)
        .values("paid_at__date")
        .annotate(total=Sum("amount_minor"))
    )
    totals_by_date = {row["paid_at__date"]: row["total"] for row in rows}

    series = []
    cursor = start_date
    today = timezone.localdate()
    while cursor <= today:
        series.append({"date": cursor, "amount_minor": totals_by_date.get(cursor) or 0})
        cursor += timedelta(days=1)
    return series


def attendance_heatmap(attendance_qs: QuerySet, days: int = 7) -> dict:
    start_date = timezone.localdate() - timedelta(days=days - 1)
    today = timezone.localdate()
    dates: list[date] = []
    cursor = start_date
    while cursor <= today:
        dates.append(cursor)
        cursor += timedelta(days=1)

    rows = (
        attendance_qs.filter(date__gte=start_date, date__lte=today)
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


def top_defaulters(invoice_qs: QuerySet, limit: int = 5) -> list[dict]:
    today = timezone.localdate()
    overdue_invoices = (
        invoice_qs.filter(status__in=["issued", "partially_paid"], due_date__lt=today)
        .annotate(
            paid_minor=Coalesce(
                Sum("payments__amount_minor", filter=Q(payments__status="successful")), Value(0)
            )
        )
        .select_related("student")
    )

    # One overdue student can have several overdue invoices — combine them
    # into a single ranked row rather than listing the same student
    # multiple times. The set of currently-overdue invoices is small by
    # nature (a live delinquency list, not full billing history), so this
    # Python-side merge stays cheap.
    by_student: dict[int, dict] = {}
    for invoice in overdue_invoices:
        outstanding = invoice.total_minor - invoice.paid_minor
        if outstanding <= 0:
            continue
        days_overdue = (today - invoice.due_date).days
        entry = by_student.setdefault(
            invoice.student_id,
            {
                "student_public_id": str(invoice.student.public_id),
                "student_name": str(invoice.student),
                "outstanding_minor": 0,
                "days_overdue": 0,
            },
        )
        entry["outstanding_minor"] += outstanding
        entry["days_overdue"] = max(entry["days_overdue"], days_overdue)

    return sorted(by_student.values(), key=lambda entry: -entry["outstanding_minor"])[:limit]
