"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.core.storage import save_document, validate_upload
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


def attach_question_image(
    *, question: Question, actor, file_name: str, content: bytes, content_type: str
) -> Question:
    """Validates (MIME + magic bytes + size, per §14) and stores a diagram/
    figure a teacher attaches to a question, e.g. "label the diagram below".
    """
    validate_upload(content=content, content_type=content_type)
    key = save_document(
        key_prefix=f"question-images/{question.organization_id}",
        filename=file_name,
        content=content,
        content_type=content_type,
    )
    question.image_storage_key = key
    question.updated_by = actor
    question.save(update_fields=["image_storage_key", "updated_by", "updated_at"])
    return question


def remove_question_image(*, question: Question, actor) -> Question:
    question.image_storage_key = ""
    question.updated_by = actor
    question.save(update_fields=["image_storage_key", "updated_by", "updated_at"])
    return question
