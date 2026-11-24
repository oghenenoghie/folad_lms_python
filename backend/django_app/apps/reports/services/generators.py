"""One function per report_type, each returning the same generic tabular
shape (title, headers, rows) — see services/exporters.py for the single
shared renderer that turns that shape into csv/xlsx/pdf, so adding a new
report_type never means writing three new format-specific functions.
"""
from apps.academics.models import Enrollment
from apps.attendance.models import Attendance
from apps.examinations.models import Result
from apps.finance.models import Invoice
from apps.finance.services.invoice_service import amount_paid_net_minor
from apps.reports.services.exceptions import UnknownReportType
from apps.students.models import Student


def student_list(*, school, parameters: dict):
    students = Student.objects.filter(school=school, deleted_at__isnull=True)
    class_arm_id = parameters.get("class_arm_id")
    if class_arm_id:
        students = students.filter(
            enrollments__class_arm__public_id=class_arm_id, enrollments__status="active"
        )
    headers = ["Admission Number", "First Name", "Last Name", "Gender", "Status"]
    rows = [
        [s.admission_number, s.first_name, s.last_name, s.gender, s.enrollment_status]
        for s in students.order_by("last_name", "first_name")
    ]
    return "Student List", headers, rows


def attendance_summary(*, school, parameters: dict):
    enrollments = Enrollment.objects.filter(class_arm__class_level__campus__school=school)
    term_id = parameters.get("term_id")
    date_from = parameters.get("date_from")
    date_to = parameters.get("date_to")
    if term_id:
        enrollments = enrollments.filter(academic_year__terms__public_id=term_id)

    headers = ["Student", "Present", "Absent", "Late", "Excused"]
    rows = []
    for enrollment in enrollments.select_related("student").distinct():
        records = Attendance.objects.filter(enrollment=enrollment)
        if date_from:
            records = records.filter(date__gte=date_from)
        if date_to:
            records = records.filter(date__lte=date_to)
        counts = {status: records.filter(status=status).count() for status in ("present", "absent", "late", "excused")}
        rows.append(
            [
                f"{enrollment.student.first_name} {enrollment.student.last_name}",
                counts["present"], counts["absent"], counts["late"], counts["excused"],
            ]
        )
    return "Attendance Summary", headers, rows


def fee_collection(*, school, parameters: dict):
    invoices = Invoice.objects.filter(school=school, deleted_at__isnull=True).select_related("student")
    term_id = parameters.get("term_id")
    if term_id:
        invoices = invoices.filter(term__public_id=term_id)

    headers = ["Invoice Number", "Student", "Total", "Status", "Amount Paid"]
    rows = [
        [
            invoice.invoice_number,
            f"{invoice.student.first_name} {invoice.student.last_name}",
            invoice.total_minor,
            invoice.status,
            amount_paid_net_minor(invoice),
        ]
        for invoice in invoices.order_by("-created_at")
    ]
    return "Fee Collection", headers, rows


def results_summary(*, school, parameters: dict):
    results = Result.objects.filter(
        assessment__class_subject__class_arm__class_level__campus__school=school,
        status="published",
    ).select_related("student", "assessment__class_subject__subject")
    term_id = parameters.get("term_id")
    if term_id:
        results = results.filter(assessment__term__public_id=term_id)

    headers = ["Student", "Subject", "Score", "Grade"]
    rows = [
        [
            f"{r.student.first_name} {r.student.last_name}",
            r.assessment.class_subject.subject.name,
            r.score,
            r.grade,
        ]
        for r in results.order_by("student__last_name")
    ]
    return "Results Summary", headers, rows


GENERATORS = {
    "student_list": student_list,
    "attendance_summary": attendance_summary,
    "fee_collection": fee_collection,
    "results_summary": results_summary,
}


def generate_table(*, report_type: str, school, parameters: dict):
    generator = GENERATORS.get(report_type)
    if generator is None:
        raise UnknownReportType(f"unknown report_type: {report_type!r}")
    return generator(school=school, parameters=parameters)
