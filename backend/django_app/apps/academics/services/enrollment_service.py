"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.academics.models import ClassArm, Enrollment
from apps.schools.models import AcademicYear
from apps.students.models import Student


def create_enrollment(
    *, student: Student, class_arm: ClassArm, academic_year: AcademicYear, actor, **fields
) -> Enrollment:
    return Enrollment.objects.create(
        organization=student.organization,
        student=student,
        class_arm=class_arm,
        academic_year=academic_year,
        created_by=actor,
        updated_by=actor,
        **fields,
    )


def update_enrollment(*, enrollment: Enrollment, actor, **fields) -> Enrollment:
    for field, value in fields.items():
        setattr(enrollment, field, value)
    enrollment.updated_by = actor
    enrollment.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return enrollment


def delete_enrollment(*, enrollment: Enrollment, actor) -> None:
    enrollment.deleted_at = timezone.now()
    enrollment.updated_by = actor
    enrollment.save(update_fields=["deleted_at", "updated_by", "updated_at"])
