"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.academics.models import Subject
from apps.schools.models import School


def create_subject(*, school: School, actor, **fields) -> Subject:
    return Subject.objects.create(
        organization=school.organization, school=school, created_by=actor, updated_by=actor, **fields
    )


def update_subject(*, subject: Subject, actor, **fields) -> Subject:
    for field, value in fields.items():
        setattr(subject, field, value)
    subject.updated_by = actor
    subject.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return subject


def delete_subject(*, subject: Subject, actor) -> None:
    subject.deleted_at = timezone.now()
    subject.updated_by = actor
    subject.save(update_fields=["deleted_at", "updated_by", "updated_at"])
