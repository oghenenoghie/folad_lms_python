"""Thin views, fat services (§11 ARCHITECTURE.md). Requesting a report card
twice for the same student/term reuses the same row (uq_report_card_student_term)
and simply re-enqueues generation rather than erroring.
"""
from apps.examinations.models import ReportCard
from apps.examinations.tasks.reports import generate_report_card_pdf
from apps.schools.models import AcademicYear, Term
from apps.students.models import Student


def request_report_card(
    *, student: Student, academic_year: AcademicYear, term: Term, actor
) -> ReportCard:
    report_card, _ = ReportCard.objects.get_or_create(
        student=student,
        term=term,
        defaults={
            "organization": student.organization,
            "academic_year": academic_year,
            "created_by": actor,
            "updated_by": actor,
        },
    )
    report_card.status = "pending"
    report_card.error_message = ""
    report_card.updated_by = actor
    report_card.save(update_fields=["status", "error_message", "updated_by", "updated_at"])
    generate_report_card_pdf.delay(report_card.id, report_card.organization_id)
    return report_card
