"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.examinations.models import Exam
from apps.schools.models import Term


def create_exam(*, term: Term, actor, **fields) -> Exam:
    return Exam.objects.create(
        organization=term.organization,
        school=term.academic_year.school,
        academic_year=term.academic_year,
        term=term,
        created_by=actor,
        updated_by=actor,
        **fields,
    )


def update_exam(*, exam: Exam, actor, **fields) -> Exam:
    for field, value in fields.items():
        setattr(exam, field, value)
    exam.updated_by = actor
    exam.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return exam


def delete_exam(*, exam: Exam, actor) -> None:
    exam.deleted_at = timezone.now()
    exam.updated_by = actor
    exam.save(update_fields=["deleted_at", "updated_by", "updated_at"])
