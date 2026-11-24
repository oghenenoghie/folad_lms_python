"""Thin views, fat services (§11 ARCHITECTURE.md). No client-facing update
to `status` here — that only ever changes as a side effect of allocating/
vacating a bed (see allocation_service)."""
from django.utils import timezone

from apps.hostel.models import HostelBed, HostelRoom


def create_bed(*, room: HostelRoom, actor, **fields) -> HostelBed:
    return HostelBed.objects.create(
        organization=room.organization, room=room, created_by=actor, updated_by=actor, **fields
    )


def update_bed(*, bed: HostelBed, actor, **fields) -> HostelBed:
    for field, value in fields.items():
        setattr(bed, field, value)
    bed.updated_by = actor
    bed.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return bed


def delete_bed(*, bed: HostelBed, actor) -> None:
    bed.deleted_at = timezone.now()
    bed.updated_by = actor
    bed.save(update_fields=["deleted_at", "updated_by", "updated_at"])
