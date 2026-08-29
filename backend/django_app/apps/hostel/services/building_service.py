"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.hostel.models import Hostel, HostelBuilding


def create_building(*, hostel: Hostel, actor, **fields) -> HostelBuilding:
    return HostelBuilding.objects.create(
        organization=hostel.organization, hostel=hostel, created_by=actor, updated_by=actor, **fields
    )


def update_building(*, building: HostelBuilding, actor, **fields) -> HostelBuilding:
    for field, value in fields.items():
        setattr(building, field, value)
    building.updated_by = actor
    building.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return building


def delete_building(*, building: HostelBuilding, actor) -> None:
    building.deleted_at = timezone.now()
    building.updated_by = actor
    building.save(update_fields=["deleted_at", "updated_by", "updated_at"])
