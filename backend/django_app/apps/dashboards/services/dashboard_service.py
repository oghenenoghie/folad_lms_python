"""Thin views, fat services (§11 ARCHITECTURE.md). §19's named risk for this
module is "query efficiency; avoiding overload" — every number below comes
from an aggregate (.count()/.aggregate()/.values().annotate()) against the
DB, never a Python loop summing fetched rows, with the sole exception of a
guardian's own (typically 1-3) children and a student's own (typically a
handful of) open invoices, where a short per-row loop is the more readable
choice and carries no list-view-scale cost.
"""
import datetime

from django.db.models import Count, Sum
from django.utils import timezone

from apps.academics.models import ClassSubject, Enrollment
from apps.assignments.models import Assignment, AssignmentSubmission
from apps.attendance.models import Attendance
from apps.examinations.models import Result
from apps.finance.models import Invoice, LedgerEntry
from apps.finance.services.invoice_service import amount_paid_net_minor
from apps.hostel.models import HostelIncident
from apps.library.models import LibraryLoan
from apps.schools.models import Term
from apps.timetable.models import TimetableSlot


def get_summary(*, user) -> dict:
    student = getattr(user, "student_profile", None)
    if student is not None:
        return {"role": "student", **_student_summary(student)}

    staff = getattr(user, "staff_profile", None)
    if staff is not None:
        teacher = getattr(staff, "teacher_profile", None)
        if teacher is not None:
            return {"role": "teacher", **_teacher_summary(teacher)}
        return {"role": "staff", "position": staff.position}

    guardian = getattr(user, "guardian_profile", None)
    if guardian is not None:
        return {"role": "guardian", **_guardian_summary(guardian)}

    return {"role": "admin", **_admin_summary(user.organization)}


def _current_term(school):
    return Term.objects.filter(academic_year__school=school, is_current=True).first()


def _attendance_breakdown(*, student) -> dict:
    counts = (
        Attendance.objects.filter(enrollment__student=student)
        .values("status")
        .annotate(count=Count("id"))
    )
    return {row["status"]: row["count"] for row in counts}


def _outstanding_fees_minor(*, student) -> int:
    open_invoices = Invoice.objects.filter(student=student, status__in=["issued", "partially_paid"])
    return sum(invoice.total_minor - amount_paid_net_minor(invoice) for invoice in open_invoices)


def _student_summary(student) -> dict:
    term = _current_term(student.school)
    upcoming_assignments = Assignment.objects.filter(
        class_subject__class_arm__enrollments__student=student,
        class_subject__class_arm__enrollments__status="active",
        due_date__gte=timezone.now().date(),
    ).exclude(submissions__student=student).distinct().count()
    published_results = Result.objects.filter(student=student, status="published")
    if term:
        published_results = published_results.filter(assessment__term=term)

    return {
        "attendance": _attendance_breakdown(student=student),
        "upcoming_assignments": upcoming_assignments,
        "published_results_count": published_results.count(),
        "outstanding_fees_minor": _outstanding_fees_minor(student=student),
    }


def _teacher_summary(teacher) -> dict:
    today_weekday = timezone.now().strftime("%A").lower()
    return {
        "class_subjects_count": ClassSubject.objects.filter(teacher=teacher, is_active=True).count(),
        "students_taught_count": Enrollment.objects.filter(
            class_arm__class_subjects__teacher=teacher, status="active"
        ).distinct().count(),
        "pending_grading_count": AssignmentSubmission.objects.filter(
            assignment__class_subject__teacher=teacher, status__in=["submitted", "late"]
        ).count(),
        "todays_periods_count": TimetableSlot.objects.filter(
            teacher=teacher, day_of_week=today_weekday, is_active=True
        ).count(),
    }


def _guardian_summary(guardian) -> dict:
    from apps.students.models import Student

    children = Student.objects.filter(guardian_links__guardian=guardian, deleted_at__isnull=True).distinct()
    return {
        "children": [
            {
                "student": str(child.public_id),
                "name": f"{child.first_name} {child.last_name}",
                "attendance": _attendance_breakdown(student=child),
                "outstanding_fees_minor": _outstanding_fees_minor(student=child),
            }
            for child in children
        ]
    }


def _admin_summary(organization) -> dict:
    from apps.staff.models import Staff
    from apps.students.models import Student

    ledger_totals = LedgerEntry.objects.filter(account="accounts_receivable").aggregate(
        debit=Sum("debit_minor"), credit=Sum("credit_minor")
    )
    net_receivable_minor = (ledger_totals["debit"] or 0) - (ledger_totals["credit"] or 0)

    return {
        "total_students": Student.objects.filter(deleted_at__isnull=True).count(),
        "total_staff": Staff.objects.filter(deleted_at__isnull=True).count(),
        "active_enrollments": Enrollment.objects.filter(status="active").count(),
        "net_receivable_minor": net_receivable_minor,
        "open_hostel_incidents": HostelIncident.objects.filter(status="open").count(),
        "overdue_library_loans": LibraryLoan.objects.filter(
            status="borrowed", due_date__lt=datetime.date.today()
        ).count(),
    }
