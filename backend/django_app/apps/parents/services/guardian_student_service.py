"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.parents.models import Guardian, GuardianStudent
from apps.students.models import Student


def link_guardian(*, guardian: Guardian, student: Student, actor, **fields) -> GuardianStudent:
    return GuardianStudent.objects.create(
        organization=guardian.organization,
        guardian=guardian,
        student=student,
        created_by=actor,
        updated_by=actor,
        **fields,
    )


def update_guardian_link(*, link: GuardianStudent, actor, **fields) -> GuardianStudent:
    for field, value in fields.items():
        setattr(link, field, value)
    link.updated_by = actor
    link.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return link


def unlink_guardian(*, link: GuardianStudent, actor) -> None:
    link.deleted_at = timezone.now()
    link.updated_by = actor
    link.save(update_fields=["deleted_at", "updated_by", "updated_at"])
