"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.schools.models import School
from apps.staff.models import Staff


def create_staff(*, school: School, actor, **fields) -> Staff:
    return Staff.objects.create(
        organization=school.organization, school=school, created_by=actor, updated_by=actor, **fields
    )


def update_staff(*, staff: Staff, actor, **fields) -> Staff:
    for field, value in fields.items():
        setattr(staff, field, value)
    staff.updated_by = actor
    staff.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return staff


def delete_staff(*, staff: Staff, actor) -> None:
    staff.deleted_at = timezone.now()
    staff.updated_by = actor
    staff.save(update_fields=["deleted_at", "updated_by", "updated_at"])
