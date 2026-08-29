"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.academics.models import ClassSubject
from apps.examinations.models import Exam, ExamSchedule


def create_exam_schedule(*, exam: Exam, class_subject: ClassSubject, actor, **fields) -> ExamSchedule:
    return ExamSchedule.objects.create(
        organization=exam.organization,
        exam=exam,
        class_subject=class_subject,
        created_by=actor,
        updated_by=actor,
        **fields,
    )


def update_exam_schedule(*, exam_schedule: ExamSchedule, actor, **fields) -> ExamSchedule:
    for field, value in fields.items():
        setattr(exam_schedule, field, value)
    exam_schedule.updated_by = actor
    exam_schedule.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return exam_schedule


def delete_exam_schedule(*, exam_schedule: ExamSchedule, actor) -> None:
    exam_schedule.deleted_at = timezone.now()
    exam_schedule.updated_by = actor
    exam_schedule.save(update_fields=["deleted_at", "updated_by", "updated_at"])
