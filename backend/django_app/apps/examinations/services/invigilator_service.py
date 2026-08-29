"""Thin views, fat services (§11 ARCHITECTURE.md). No update: reassigning
an invigilator is an unassign-then-assign, not an in-place edit — there's
nothing on this model besides the exam_schedule/teacher pair itself.
"""
from django.utils import timezone

from apps.examinations.models import ExamSchedule, Invigilator
from apps.staff.models import Teacher


def assign_invigilator(*, exam_schedule: ExamSchedule, teacher: Teacher, actor) -> Invigilator:
    return Invigilator.objects.create(
        organization=exam_schedule.organization,
        exam_schedule=exam_schedule,
        teacher=teacher,
        created_by=actor,
        updated_by=actor,
    )


def unassign_invigilator(*, invigilator: Invigilator, actor) -> None:
    invigilator.deleted_at = timezone.now()
    invigilator.updated_by = actor
    invigilator.save(update_fields=["deleted_at", "updated_by", "updated_at"])
