"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.examinations.models import GradingScheme
from apps.schools.models import School


def create_grading_scheme(*, school: School, actor, **fields) -> GradingScheme:
    return GradingScheme.objects.create(
        organization=school.organization, school=school, created_by=actor, updated_by=actor, **fields
    )


def update_grading_scheme(*, grading_scheme: GradingScheme, actor, **fields) -> GradingScheme:
    for field, value in fields.items():
        setattr(grading_scheme, field, value)
    grading_scheme.updated_by = actor
    grading_scheme.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return grading_scheme


def delete_grading_scheme(*, grading_scheme: GradingScheme, actor) -> None:
    grading_scheme.deleted_at = timezone.now()
    grading_scheme.updated_by = actor
    grading_scheme.save(update_fields=["deleted_at", "updated_by", "updated_at"])
