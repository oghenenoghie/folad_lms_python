"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.schools.models import School
from apps.timetable.models import Period


def create_period(*, school: School, actor, **fields) -> Period:
    return Period.objects.create(
        organization=school.organization, school=school, created_by=actor, updated_by=actor, **fields
    )


def update_period(*, period: Period, actor, **fields) -> Period:
    for field, value in fields.items():
        setattr(period, field, value)
    period.updated_by = actor
    period.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return period


def delete_period(*, period: Period, actor) -> None:
    period.deleted_at = timezone.now()
    period.updated_by = actor
    period.save(update_fields=["deleted_at", "updated_by", "updated_at"])
