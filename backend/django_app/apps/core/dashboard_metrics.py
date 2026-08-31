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
import calendar as calendar_module
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


def gender_breakdown(student_qs: QuerySet) -> dict[str, int]:
    """Real male/female/other/unspecified counts for the student
    distribution donut — Student.gender is a real, populated field, not a
    fabricated proportion."""
    counts = student_qs.values("gender").annotate(count=Count("id"))
    breakdown = {"male": 0, "female": 0, "other": 0, "unspecified": 0}
    for row in counts:
        key = row["gender"] or "unspecified"
        breakdown[key if key in breakdown else "other"] += row["count"]
    return breakdown


def recent_messages(message_qs: QuerySet, limit: int = 5) -> list[dict]:
    messages = message_qs.select_related("sender").order_by("-created_at")[:limit]
    return [
        {
            "sender_name": f"{m.sender.first_name} {m.sender.last_name}".strip() or m.sender.email,
            "sender_email": m.sender.email,
            "subject": m.subject,
            "preview": (m.body[:120] + "…") if len(m.body) > 120 else m.body,
            "created_at": m.created_at,
            "is_read": m.is_read,
        }
        for m in messages
    ]


def unread_message_count(message_qs: QuerySet) -> int:
    return message_qs.filter(is_read=False).count()


def recent_announcements(announcement_qs: QuerySet, limit: int = 5) -> list[dict]:
    announcements = announcement_qs.order_by("-is_pinned", "-created_at")[:limit]
    return [
        {
            "title": a.title,
            "preview": (a.body[:140] + "…") if len(a.body) > 140 else a.body,
            "audience": a.audience,
            "is_pinned": a.is_pinned,
            "published_at": a.published_at,
            "created_at": a.created_at,
        }
        for a in announcements
    ]


def recent_student_activities(submission_qs: QuerySet, limit: int = 5) -> list[dict]:
    """Recent assignment submissions — the one genuinely "student did a
    thing on this date with this status" event stream already in the
    schema, used for the dashboard's Student Activities card."""
    submissions = submission_qs.select_related("student", "assignment").order_by("-submitted_at")[:limit]
    return [
        {
            "title": f"{s.student} submitted “{s.assignment.title}”",
            "status": s.status,
            "date": s.submitted_at,
        }
        for s in submissions
    ]


def recent_notifications(notification_qs: QuerySet, limit: int = 8) -> list[dict]:
    notifications = notification_qs.order_by("-created_at")[:limit]
    return [
        {
            "title": n.title,
            "body": n.body,
            "notification_type": n.notification_type,
            "is_read": n.is_read,
            "created_at": n.created_at,
        }
        for n in notifications
    ]


def month_calendar(
    year: int,
    month: int,
    *,
    exam_schedule_qs: QuerySet,
    term_qs: QuerySet,
    announcement_qs: QuerySet,
    achievement_qs: QuerySet,
) -> dict:
    """A real month-grid calendar: every marked day carries at least one
    genuine event (an exam date, a term boundary, a published announcement,
    or an awarded achievement) — never a placeholder date."""
    month_start = date(year, month, 1)
    month_end = date(year, month, calendar_module.monthrange(year, month)[1])
    today = timezone.localdate()

    events_by_day: dict[date, list[str]] = {}

    def add_event(day: date | None, label: str) -> None:
        if day is None or day < month_start or day > month_end:
            return
        events_by_day.setdefault(day, []).append(label)

    for exam_schedule in exam_schedule_qs.filter(
        date__gte=month_start, date__lte=month_end
    ).select_related("exam"):
        add_event(exam_schedule.date, f"Exam: {exam_schedule.exam.name}")

    for term in term_qs.filter(
        Q(start_date__gte=month_start, start_date__lte=month_end)
        | Q(end_date__gte=month_start, end_date__lte=month_end)
    ):
        add_event(term.start_date, f"Term starts: {term.name}")
        add_event(term.end_date, f"Term ends: {term.name}")

    for announcement in announcement_qs.filter(
        published_at__date__gte=month_start, published_at__date__lte=month_end
    ):
        add_event(announcement.published_at.date(), f"Notice: {announcement.title}")

    for achievement in achievement_qs.filter(
        awarded_on__gte=month_start, awarded_on__lte=month_end
    ).select_related("student"):
        add_event(achievement.awarded_on, f"Achievement: {achievement.student} — {achievement.title}")

    weeks = []
    for week in calendar_module.Calendar(firstweekday=0).monthdatescalendar(year, month):
        weeks.append(
            [
                {
                    "date": day,
                    "in_month": day.month == month,
                    "is_today": day == today,
                    "events": events_by_day.get(day, []),
                }
                for day in week
            ]
        )

    return {
        "year": year,
        "month": month,
        "month_label": month_start.strftime("%B %Y"),
        "weekday_labels": [calendar_module.day_abbr[i] for i in range(7)],
        "weeks": weeks,
    }
