"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.schools.models import School
from apps.students.models import Student


def create_student(*, school: School, actor, **fields) -> Student:
    """Admission: the act of creating this record *is* the admission ->
    profile step (§18 M4 exit criteria)."""
    return Student.objects.create(
        organization=school.organization, school=school, created_by=actor, updated_by=actor, **fields
    )


def update_student(*, student: Student, actor, **fields) -> Student:
    for field, value in fields.items():
        setattr(student, field, value)
    student.updated_by = actor
    student.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return student


def delete_student(*, student: Student, actor) -> None:
    student.deleted_at = timezone.now()
    student.updated_by = actor
    student.save(update_fields=["deleted_at", "updated_by", "updated_at"])
