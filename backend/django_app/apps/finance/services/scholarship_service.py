"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.finance.models import Discount, Scholarship
from apps.schools.models import AcademicYear
from apps.students.models import Student


def award_scholarship(
    *, student: Student, discount: Discount, academic_year: AcademicYear, actor, **fields
) -> Scholarship:
    return Scholarship.objects.create(
        organization=student.organization,
        school=student.school,
        student=student,
        discount=discount,
        academic_year=academic_year,
        created_by=actor,
        updated_by=actor,
        **fields,
    )


def update_scholarship(*, scholarship: Scholarship, actor, **fields) -> Scholarship:
    for field, value in fields.items():
        setattr(scholarship, field, value)
    scholarship.updated_by = actor
    scholarship.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return scholarship


def revoke_scholarship(*, scholarship: Scholarship, actor) -> None:
    scholarship.deleted_at = timezone.now()
    scholarship.updated_by = actor
    scholarship.save(update_fields=["deleted_at", "updated_by", "updated_at"])
