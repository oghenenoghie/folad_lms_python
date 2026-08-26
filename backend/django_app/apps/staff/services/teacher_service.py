"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.staff.models import Staff, Teacher


def create_teacher_profile(*, staff: Staff, actor, **fields) -> Teacher:
    return Teacher.objects.create(
        organization=staff.organization, staff=staff, created_by=actor, updated_by=actor, **fields
    )


def update_teacher_profile(*, teacher: Teacher, actor, **fields) -> Teacher:
    for field, value in fields.items():
        setattr(teacher, field, value)
    teacher.updated_by = actor
    teacher.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return teacher


def delete_teacher_profile(*, teacher: Teacher, actor) -> None:
    teacher.deleted_at = timezone.now()
    teacher.updated_by = actor
    teacher.save(update_fields=["deleted_at", "updated_by", "updated_at"])
