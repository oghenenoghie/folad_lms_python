"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.academics.models import ClassSubject
from apps.examinations.models import Assessment
from apps.schools.models import Term


def create_assessment(*, class_subject: ClassSubject, term: Term, actor, **fields) -> Assessment:
    return Assessment.objects.create(
        organization=class_subject.organization,
        class_subject=class_subject,
        term=term,
        created_by=actor,
        updated_by=actor,
        **fields,
    )


def update_assessment(*, assessment: Assessment, actor, **fields) -> Assessment:
    for field, value in fields.items():
        setattr(assessment, field, value)
    assessment.updated_by = actor
    assessment.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return assessment


def delete_assessment(*, assessment: Assessment, actor) -> None:
    assessment.deleted_at = timezone.now()
    assessment.updated_by = actor
    assessment.save(update_fields=["deleted_at", "updated_by", "updated_at"])
