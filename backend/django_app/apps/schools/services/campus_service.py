"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.schools.models import Campus, School


def create_campus(*, school: School, actor, **fields) -> Campus:
    return Campus.objects.create(
        organization=school.organization, school=school, created_by=actor, updated_by=actor, **fields
    )


def update_campus(*, campus: Campus, actor, **fields) -> Campus:
    for field, value in fields.items():
        setattr(campus, field, value)
    campus.updated_by = actor
    campus.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return campus


def delete_campus(*, campus: Campus, actor) -> None:
    campus.deleted_at = timezone.now()
    campus.updated_by = actor
    campus.save(update_fields=["deleted_at", "updated_by", "updated_at"])
