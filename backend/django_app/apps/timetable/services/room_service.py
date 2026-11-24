"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.schools.models import Campus
from apps.timetable.models import Room


def create_room(*, campus: Campus, actor, **fields) -> Room:
    return Room.objects.create(
        organization=campus.organization, campus=campus, created_by=actor, updated_by=actor, **fields
    )


def update_room(*, room: Room, actor, **fields) -> Room:
    for field, value in fields.items():
        setattr(room, field, value)
    room.updated_by = actor
    room.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return room


def delete_room(*, room: Room, actor) -> None:
    room.deleted_at = timezone.now()
    room.updated_by = actor
    room.save(update_fields=["deleted_at", "updated_by", "updated_at"])
