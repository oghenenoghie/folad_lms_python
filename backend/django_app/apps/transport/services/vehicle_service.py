"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.schools.models import School
from apps.transport.models import Vehicle


def create_vehicle(*, school: School, actor, **fields) -> Vehicle:
    return Vehicle.objects.create(
        organization=school.organization, school=school, created_by=actor, updated_by=actor, **fields
    )


def update_vehicle(*, vehicle: Vehicle, actor, **fields) -> Vehicle:
    for field, value in fields.items():
        setattr(vehicle, field, value)
    vehicle.updated_by = actor
    vehicle.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return vehicle


def delete_vehicle(*, vehicle: Vehicle, actor) -> None:
    vehicle.deleted_at = timezone.now()
    vehicle.updated_by = actor
    vehicle.save(update_fields=["deleted_at", "updated_by", "updated_at"])
