"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.examinations.models import GradeBand, GradingScheme


def create_grade_band(*, grading_scheme: GradingScheme, actor, **fields) -> GradeBand:
    return GradeBand.objects.create(
        organization=grading_scheme.organization,
        grading_scheme=grading_scheme,
        created_by=actor,
        updated_by=actor,
        **fields,
    )


def update_grade_band(*, grade_band: GradeBand, actor, **fields) -> GradeBand:
    for field, value in fields.items():
        setattr(grade_band, field, value)
    grade_band.updated_by = actor
    grade_band.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return grade_band


def delete_grade_band(*, grade_band: GradeBand, actor) -> None:
    grade_band.deleted_at = timezone.now()
    grade_band.updated_by = actor
    grade_band.save(update_fields=["deleted_at", "updated_by", "updated_at"])
