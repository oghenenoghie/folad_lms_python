"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.hostel.models import Hostel
from apps.schools.models import School


def create_hostel(*, school: School, actor, **fields) -> Hostel:
    return Hostel.objects.create(
        organization=school.organization, school=school, created_by=actor, updated_by=actor, **fields
    )


def update_hostel(*, hostel: Hostel, actor, **fields) -> Hostel:
    for field, value in fields.items():
        setattr(hostel, field, value)
    hostel.updated_by = actor
    hostel.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return hostel


def delete_hostel(*, hostel: Hostel, actor) -> None:
    hostel.deleted_at = timezone.now()
    hostel.updated_by = actor
    hostel.save(update_fields=["deleted_at", "updated_by", "updated_at"])
