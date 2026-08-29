"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.examinations.models import Question, QuestionOption


def create_question_option(*, question: Question, actor, **fields) -> QuestionOption:
    return QuestionOption.objects.create(
        organization=question.organization,
        question=question,
        created_by=actor,
        updated_by=actor,
        **fields,
    )


def update_question_option(*, question_option: QuestionOption, actor, **fields) -> QuestionOption:
    for field, value in fields.items():
        setattr(question_option, field, value)
    question_option.updated_by = actor
    question_option.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return question_option


def delete_question_option(*, question_option: QuestionOption, actor) -> None:
    question_option.deleted_at = timezone.now()
    question_option.updated_by = actor
    question_option.save(update_fields=["deleted_at", "updated_by", "updated_at"])
