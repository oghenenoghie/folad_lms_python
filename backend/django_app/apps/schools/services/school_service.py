"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.schools.models import School


def create_school(*, actor, **fields) -> School:
    return School.objects.create(organization=actor.organization, created_by=actor, updated_by=actor, **fields)


def update_school(*, school: School, actor, **fields) -> School:
    for field, value in fields.items():
        setattr(school, field, value)
    school.updated_by = actor
    school.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return school


def delete_school(*, school: School, actor) -> None:
    school.deleted_at = timezone.now()
    school.updated_by = actor
    school.save(update_fields=["deleted_at", "updated_by", "updated_at"])
