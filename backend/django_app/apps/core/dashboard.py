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
per-staff productivity scoring) are deliberately not here: none of that
data exists anywhere in this schema, and inventing plausible-looking
numbers for them would be worse than not showing them.
"""
import json

from django.core.cache import cache
from django.http import HttpRequest
from django.utils import timezone

from apps.accounts.models import LoginHistory
from apps.assignments.models import AssignmentSubmission
from apps.attendance.models import Attendance
from apps.communication.models import Announcement, Message, Notification
from apps.core import dashboard_metrics as metrics
from apps.examinations.models import ExamSchedule
from apps.finance.models import Invoice, Payment
from apps.schools.models import Term
from apps.staff.models import Staff, Teacher
from apps.students.models import Achievement, Student
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


def _monthly_enrollment_chart_json() -> str:
    series = metrics.enrollment_monthly_series(Student.all_tenants)
    return _line_chart_json([row["label"] for row in series], [row["count"] for row in series], "New students")


def _weekly_enrollment_chart_json() -> str:
    series = metrics.enrollment_weekly_series(Student.all_tenants)
    return _line_chart_json([row["label"] for row in series], [row["count"] for row in series], "New students")


def _line_chart_json(labels: list[str], values: list[int], label: str) -> str:
    return json.dumps(
        {
            "labels": labels,
            "datasets": [
                {
                    "label": label,
                    "data": values,
                    "borderColor": "var(--color-primary-600)",
                    "backgroundColor": "var(--color-primary-600)",
                    "tension": 0.4,
                    "fill": False,
                }
            ],
        }
    )


def _gender_donut_json(breakdown: dict[str, int]) -> str:
    labels = {"male": "Male", "female": "Female", "other": "Other", "unspecified": "Unspecified"}
    colors = {
        "male": "#3b82f6",
        "female": "#f59e0b",
        "other": "#8b5cf6",
        "unspecified": "#cbd5e1",
    }
    keys = [k for k in ("male", "female", "other", "unspecified") if breakdown.get(k)]
    return json.dumps(
        {
            "labels": [labels[k] for k in keys],
            "datasets": [
                {
                    "data": [breakdown[k] for k in keys],
                    "backgroundColor": [colors[k] for k in keys],
                    "borderWidth": 0,
                }
            ],
        }
    )


DASHBOARD_CALLBACK_CACHE_KEY = "dashboard:admin_callback_context:v1"
DASHBOARD_CALLBACK_CACHE_TTL_SECONDS = 60


def dashboard_callback(request: HttpRequest, context: dict) -> dict:
    """Every widget below is its own aggregate query (~20 total) — cached
    for a short TTL since this runs on every /admin/ index page view and
    none of these numbers need to be more real-time than "up to a minute
    old". Cached value is plain dicts/strings only (see
    _compute_dashboard_context), never model instances, so it's cheap to
    pickle and never goes stale in an unpicklable way.
    """
    extra = cache.get(DASHBOARD_CALLBACK_CACHE_KEY)
    if extra is None:
        extra = _compute_dashboard_context()
        cache.set(DASHBOARD_CALLBACK_CACHE_KEY, extra, DASHBOARD_CALLBACK_CACHE_TTL_SECONDS)
    context.update(extra)
    return context


def _compute_dashboard_context() -> dict:
    today = timezone.localdate()
    attendance_pct = metrics.attendance_today_pct(Attendance.all_tenants)
    gender_breakdown = metrics.gender_breakdown(Student.all_tenants)
    context: dict = {}

    # Primary KPI row — matches the requested layout: 3 warm-accent cards
    # plus a strong-accent 4th card, all real counts.
    context["kpi_cards"] = [
        {"title": "Total Students", "value": Student.all_tenants.count(), "icon": "groups", "tone": "amber"},
        {"title": "Total Teachers", "value": Teacher.all_tenants.count(), "icon": "cast_for_education", "tone": "amber"},
        {"title": "Total Staff", "value": Staff.all_tenants.count(), "icon": "badge", "tone": "amber"},
        {"title": "Achievements", "value": Achievement.all_tenants.count(), "icon": "emoji_events", "tone": "blue"},
    ]

    context["student_gender_breakdown"] = gender_breakdown
    context["student_gender_total"] = sum(gender_breakdown.values())
    context["student_gender_chart_json"] = _gender_donut_json(gender_breakdown)

    context["enrollment_chart_json_monthly"] = _monthly_enrollment_chart_json()
    context["enrollment_chart_json_weekly"] = _weekly_enrollment_chart_json()

    weekly_attendance = metrics.weekly_attendance_series(Attendance.all_tenants)
    context["weekly_attendance_chart_json"] = json.dumps(
        {
            "labels": [d["label"] for d in weekly_attendance["days"]],
            "datasets": [
                {
                    "label": "Present %",
                    "data": [d["present_pct"] for d in weekly_attendance["days"]],
                    "backgroundColor": "#3b82f6",
                    "borderRadius": 4,
                },
                {
                    "label": "Absent %",
                    "data": [d["absent_pct"] for d in weekly_attendance["days"]],
                    "backgroundColor": "#f59e0b",
                    "borderRadius": 4,
                },
            ],
        }
    )
    context["weekly_attendance_present_pct"] = weekly_attendance["present_pct"]
    context["weekly_attendance_absent_pct"] = weekly_attendance["absent_pct"]

    context["student_activities"] = metrics.recent_student_activities(AssignmentSubmission.all_tenants)

    context["recent_messages"] = metrics.recent_messages(Message.all_tenants)
    context["unread_message_count"] = metrics.unread_message_count(Message.all_tenants)

    context["notices"] = metrics.recent_announcements(Announcement.all_tenants)
    context["recent_activity"] = metrics.recent_notifications(Notification.all_tenants)

    context["calendar"] = metrics.month_calendar(
        today.year,
        today.month,
        exam_schedule_qs=ExamSchedule.all_tenants,
        term_qs=Term.all_tenants,
        announcement_qs=Announcement.all_tenants,
        achievement_qs=Achievement.all_tenants,
    )

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
    context["revenue_chart_json"] = _revenue_chart_json()
    context["attendance_heatmap"] = metrics.attendance_heatmap(Attendance.all_tenants)
    context["top_defaulters"] = metrics.top_defaulters(Invoice.all_tenants)

    # Plain dicts rather than model instances — keeps the cached value
    # simple to pickle and independent of any later field/relation changes
    # on LoginHistory/User/Organization.
    context["recent_logins"] = [
        {
            "user": {"email": login.user.email},
            "organization": str(login.organization) if login.organization_id else None,
            "success": login.success,
            "created_at": login.created_at,
        }
        for login in LoginHistory.all_tenants.select_related("user", "organization").order_by("-created_at")[:8]
    ]

    return context
