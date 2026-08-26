"""Thin views, fat services (§11 ARCHITECTURE.md). `class_arm`/`teacher`
are always derived from `class_subject` here, never accepted from client
input — see models.py's module docstring on why that denormalization is
what turns double-booking into a real database constraint.
"""
from django.utils import timezone

from apps.academics.models import ClassSubject
from apps.timetable.models import TimetableSlot


def create_timetable_slot(*, class_subject: ClassSubject, actor, **fields) -> TimetableSlot:
    return TimetableSlot.objects.create(
        organization=class_subject.organization,
        class_subject=class_subject,
        class_arm=class_subject.class_arm,
        teacher=class_subject.teacher,
        created_by=actor,
        updated_by=actor,
        **fields,
    )


def update_timetable_slot(*, timetable_slot: TimetableSlot, actor, **fields) -> TimetableSlot:
    for field, value in fields.items():
        setattr(timetable_slot, field, value)
    timetable_slot.updated_by = actor
    timetable_slot.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return timetable_slot


def delete_timetable_slot(*, timetable_slot: TimetableSlot, actor) -> None:
    timetable_slot.deleted_at = timezone.now()
    timetable_slot.updated_by = actor
    timetable_slot.save(update_fields=["deleted_at", "updated_by", "updated_at"])
