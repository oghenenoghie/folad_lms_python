"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.hostel.models import HostelBuilding, HostelRoom


def create_room(*, building: HostelBuilding, actor, **fields) -> HostelRoom:
    return HostelRoom.objects.create(
        organization=building.organization, building=building, created_by=actor, updated_by=actor, **fields
    )


def update_room(*, room: HostelRoom, actor, **fields) -> HostelRoom:
    for field, value in fields.items():
        setattr(room, field, value)
    room.updated_by = actor
    room.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return room


def delete_room(*, room: HostelRoom, actor) -> None:
    room.deleted_at = timezone.now()
    room.updated_by = actor
    room.save(update_fields=["deleted_at", "updated_by", "updated_at"])
