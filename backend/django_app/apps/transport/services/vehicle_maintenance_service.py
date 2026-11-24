"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.transport.models import Vehicle, VehicleMaintenance


def schedule_maintenance(*, vehicle: Vehicle, actor, **fields) -> VehicleMaintenance:
    return VehicleMaintenance.objects.create(
        organization=vehicle.organization, vehicle=vehicle, created_by=actor, updated_by=actor, **fields
    )


def update_maintenance(*, maintenance: VehicleMaintenance, actor, **fields) -> VehicleMaintenance:
    for field, value in fields.items():
        setattr(maintenance, field, value)
    maintenance.updated_by = actor
    maintenance.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return maintenance


def delete_maintenance(*, maintenance: VehicleMaintenance, actor) -> None:
    maintenance.deleted_at = timezone.now()
    maintenance.updated_by = actor
    maintenance.save(update_fields=["deleted_at", "updated_by", "updated_at"])
