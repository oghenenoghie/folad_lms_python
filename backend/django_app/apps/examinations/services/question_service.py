"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.examinations.models import Assessment, Question


def create_question(*, assessment: Assessment, actor, **fields) -> Question:
    return Question.objects.create(
        organization=assessment.organization,
        assessment=assessment,
        created_by=actor,
        updated_by=actor,
        **fields,
    )


def update_question(*, question: Question, actor, **fields) -> Question:
    for field, value in fields.items():
        setattr(question, field, value)
    question.updated_by = actor
    question.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return question


def delete_question(*, question: Question, actor) -> None:
    question.deleted_at = timezone.now()
    question.updated_by = actor
    question.save(update_fields=["deleted_at", "updated_by", "updated_at"])
