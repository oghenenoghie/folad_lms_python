"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.academics.models import ClassSubject
from apps.assignments.models import Assignment
from apps.schools.models import Term


def create_assignment(*, class_subject: ClassSubject, term: Term, actor, **fields) -> Assignment:
    return Assignment.objects.create(
        organization=class_subject.organization,
        class_subject=class_subject,
        term=term,
        created_by=actor,
        updated_by=actor,
        **fields,
    )


def update_assignment(*, assignment: Assignment, actor, **fields) -> Assignment:
    for field, value in fields.items():
        setattr(assignment, field, value)
    assignment.updated_by = actor
    assignment.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return assignment


def delete_assignment(*, assignment: Assignment, actor) -> None:
    assignment.deleted_at = timezone.now()
    assignment.updated_by = actor
    assignment.save(update_fields=["deleted_at", "updated_by", "updated_at"])
