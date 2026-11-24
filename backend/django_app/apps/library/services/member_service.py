"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.library.models import LibraryMember
from apps.schools.models import School


def create_member(*, school: School, actor, **fields) -> LibraryMember:
    return LibraryMember.objects.create(
        organization=school.organization, school=school, created_by=actor, updated_by=actor, **fields
    )


def update_member(*, member: LibraryMember, actor, **fields) -> LibraryMember:
    for field, value in fields.items():
        setattr(member, field, value)
    member.updated_by = actor
    member.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return member


def delete_member(*, member: LibraryMember, actor) -> None:
    member.deleted_at = timezone.now()
    member.updated_by = actor
    member.save(update_fields=["deleted_at", "updated_by", "updated_at"])
