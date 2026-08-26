"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.parents.models import Guardian, GuardianStudent
from apps.students.models import Student


def link_guardian_student(*, guardian: Guardian, student: Student, actor, **fields) -> GuardianStudent:
    # Both querysets used to resolve `guardian`/`student` in the view are
    # already tenant-scoped (TenantManager), so a cross-tenant pairing can't
    # reach here in practice — this is a cheap belt-and-braces check, not
    # the actual isolation boundary.
    if guardian.organization_id != student.organization_id:
        raise ValueError("guardian and student must belong to the same organization")
    return GuardianStudent.objects.create(
        organization=guardian.organization,
        guardian=guardian,
        student=student,
        created_by=actor,
        updated_by=actor,
        **fields,
    )


def update_guardian_student(*, link: GuardianStudent, actor, **fields) -> GuardianStudent:
    for field, value in fields.items():
        setattr(link, field, value)
    link.updated_by = actor
    link.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return link


def unlink_guardian_student(*, link: GuardianStudent, actor) -> None:
    link.deleted_at = timezone.now()
    link.updated_by = actor
    link.save(update_fields=["deleted_at", "updated_by", "updated_at"])
