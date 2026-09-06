"""Thin views, fat services (§11 ARCHITECTURE.md) — same convention as
apps.examinations. Owns question authoring (create/update/duplicate),
the draft->submitted->review->approved->published->archived workflow, and
immutable version snapshotting. Scoring belongs to a later phase's
scoring_service, once ExamAttempt/StudentAnswer exist to score.
"""
from decimal import Decimal, InvalidOperation

from django.db import transaction

from apps.cbt.models import (
    DIFFICULTY_CHOICES,
    QUESTION_STATUS_TRANSITIONS,
    CBTMedia,
    Question,
    QuestionBlock,
    QuestionOption,
    QuestionVersion,
    Topic,
)

# The minimum shape `QuestionBlock.content` must have per block_type,
# enforced here rather than left to the database (a JSONField accepts
# anything) or the frontend alone (an API caller isn't the editor UI).
# Deliberately loose — this catches "the block is missing its defining
# field entirely", not every semantic rule (e.g. a graph's series schema);
# tighter validation belongs to the editor UI and can be layered in later
# without a migration.
_BLOCK_REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "paragraph": ("html",),
    "heading": ("html",),
    "image": ("media_id",),
    "svg": ("media_id",),
    "equation": ("latex",),
    "chemical_equation": ("formula",),
    "table": ("rows",),
    "graph": ("type", "series"),
    "audio": ("media_id",),
    "video": ("media_id",),
    "document": ("media_id",),
    "diagram": ("media_id",),
    "callout": ("html",),
    "divider": (),
}


class QuestionError(ValueError):
    """A validation failure the caller should surface as a 4xx, not a bug."""


class InvalidQuestionTransition(QuestionError):
    pass


def validate_block_content(*, block_type: str, content: dict) -> None:
    required = _BLOCK_REQUIRED_KEYS.get(block_type)
    if required is None:
        raise QuestionError(f"unknown block_type: {block_type!r}")
    missing = [key for key in required if key not in content]
    if missing:
        raise QuestionError(f"{block_type} block content missing required key(s): {', '.join(missing)}")


def build_question_snapshot(question: Question) -> dict:
    """The full reconstructible state of a question: its own fields plus
    every block and option, in order — what a QuestionVersion or a
    duplicate needs to fully recreate the question elsewhere.
    """
    return {
        "subject_id": question.subject_id,
        "class_level_id": question.class_level_id,
        "topic_id": question.topic_id,
        "question_type": question.question_type,
        "difficulty": question.difficulty,
        "marks": str(question.marks),
        "negative_marks": str(question.negative_marks),
        "blocks": [
            {"block_type": b.block_type, "content": b.content, "order": b.order}
            for b in question.blocks.all()
        ],
        "options": [
            {
                "label": o.label,
                "content": o.content,
                "is_correct": o.is_correct,
                "order": o.order,
                "explanation": o.explanation,
            }
            for o in question.options.all()
        ],
    }


def _snapshot_question_version(question: Question) -> QuestionVersion:
    last = question.versions.first()
    next_number = (last.version_number + 1) if last else 1
    return QuestionVersion.objects.create(
        organization=question.organization,
        question=question,
        version_number=next_number,
        content=build_question_snapshot(question),
        created_by=question.updated_by,
        updated_by=question.updated_by,
    )


@transaction.atomic
def create_question(
    *, organization, actor, blocks: list[dict] | None = None, options: list[dict] | None = None, **fields
) -> Question:
    question = Question.objects.create(organization=organization, created_by=actor, updated_by=actor, **fields)
    for block in blocks or []:
        validate_block_content(block_type=block["block_type"], content=block.get("content", {}))
        QuestionBlock.objects.create(organization=organization, question=question, **block)
    for option in options or []:
        QuestionOption.objects.create(organization=organization, question=question, **option)
    return question


@transaction.atomic
def update_question(
    *,
    question: Question,
    actor,
    blocks: list[dict] | None = None,
    options: list[dict] | None = None,
    **fields,
) -> Question:
    """Editing a *published* question snapshots its current state first
    (§9/§10 of the CBT spec: never silently overwrite what a live or past
    exam already captured) — the edit then applies on top, still under
    "published", ready for the next exam snapshot to pick up.
    """
    if question.status == "published":
        question.updated_by = actor
        _snapshot_question_version(question)

    for field, value in fields.items():
        setattr(question, field, value)
    question.updated_by = actor
    question.save(update_fields=[*fields.keys(), "updated_by", "updated_at"] if fields else ["updated_by", "updated_at"])

    if blocks is not None:
        question.blocks.all().delete()
        for block in blocks:
            validate_block_content(block_type=block["block_type"], content=block.get("content", {}))
            QuestionBlock.objects.create(organization=question.organization, question=question, **block)

    if options is not None:
        question.options.all().delete()
        for option in options:
            QuestionOption.objects.create(organization=question.organization, question=question, **option)

    return question


def _transition(*, question: Question, new_status: str, actor) -> Question:
    allowed = QUESTION_STATUS_TRANSITIONS.get(question.status, set())
    if new_status not in allowed:
        raise InvalidQuestionTransition(
            f"cannot move a {question.status!r} question to {new_status!r}"
        )
    question.status = new_status
    question.updated_by = actor
    update_fields = ["status", "updated_by", "updated_at"]
    if new_status != "approved":
        question.approved_by = None if new_status == "draft" else question.approved_by
        update_fields.append("approved_by")
    question.save(update_fields=update_fields)
    return question


def submit_question(*, question: Question, actor) -> Question:
    return _transition(question=question, new_status="submitted", actor=actor)


def start_review(*, question: Question, actor) -> Question:
    return _transition(question=question, new_status="review", actor=actor)


def approve_question(*, question: Question, actor) -> Question:
    question = _transition(question=question, new_status="approved", actor=actor)
    question.approved_by = actor
    question.save(update_fields=["approved_by"])
    return question


def reject_question(*, question: Question, actor) -> Question:
    """Sends a submitted/under-review question back to draft for the
    author to rework — the spec's "Request Changes" action on the
    question-review screen.
    """
    return _transition(question=question, new_status="draft", actor=actor)


def publish_question(*, question: Question, actor) -> Question:
    return _transition(question=question, new_status="published", actor=actor)


def archive_question(*, question: Question, actor) -> Question:
    return _transition(question=question, new_status="archived", actor=actor)


@transaction.atomic
def duplicate_question(*, question: Question, actor) -> Question:
    """A fresh, independent draft copy — never a reference back to the
    original, so editing the copy can never retroactively change a
    question some exam has already snapshotted.
    """
    copy = Question.objects.create(
        organization=question.organization,
        subject=question.subject,
        class_level=question.class_level,
        topic=question.topic,
        question_type=question.question_type,
        difficulty=question.difficulty,
        marks=question.marks,
        negative_marks=question.negative_marks,
        status="draft",
        created_by=actor,
        updated_by=actor,
    )
    for block in question.blocks.all():
        QuestionBlock.objects.create(
            organization=copy.organization,
            question=copy,
            block_type=block.block_type,
            content=block.content,
            order=block.order,
        )
    for option in question.options.all():
        QuestionOption.objects.create(
            organization=copy.organization,
            question=copy,
            label=option.label,
            content=option.content,
            is_correct=option.is_correct,
            order=option.order,
            explanation=option.explanation,
        )
    return copy


def delete_question(*, question: Question, actor) -> None:
    from django.utils import timezone

    question.deleted_at = timezone.now()
    question.updated_by = actor
    question.save(update_fields=["deleted_at", "updated_by", "updated_at"])


def upload_media(
    *, organization, actor, name: str, media_type: str, file_name: str, content: bytes, content_type: str, **fields
) -> CBTMedia:
    """Image/document uploads work today; audio/video/svg need
    apps.core.storage.ALLOWED_UPLOAD_CONTENT_TYPES widened first (deferred
    to the media-library phase, once this is wired to an upload API —
    widening it now for a type nothing yet serves would be speculative).
    """
    from apps.core.storage import save_document, validate_upload

    validate_upload(content=content, content_type=content_type, max_size_bytes=50 * 1024 * 1024)
    key = save_document(
        key_prefix=f"cbt-media/{organization.id}", filename=file_name, content=content, content_type=content_type
    )
    return CBTMedia.objects.create(
        organization=organization,
        name=name,
        media_type=media_type,
        storage_key=key,
        content_type=content_type,
        size_bytes=len(content),
        created_by=actor,
        updated_by=actor,
        **fields,
    )


# Bulk import supports the flat, spreadsheet-friendly shape that covers
# the vast majority of a real question bank — single/multiple choice and
# true/false — rather than every rich-content block_type, which has no
# sensible flat-CSV representation. A question needing blocks/options
# richer than this (an image, an equation, a numeric answer key, ...)
# still goes through the ordinary create/update API.
_BULK_IMPORT_QUESTION_TYPES = {"single_choice", "multiple_choice", "true_false"}
_BULK_IMPORT_OPTION_COLUMNS = ["option_a", "option_b", "option_c", "option_d", "option_e", "option_f"]
_DIFFICULTY_CODES = {code for code, _ in DIFFICULTY_CHOICES}


def _bulk_import_choice_options(row: dict, question_type: str) -> list[dict]:
    letters = "ABCDEFGH"
    provided = []
    for i, column in enumerate(_BULK_IMPORT_OPTION_COLUMNS):
        text = (row.get(column) or "").strip()
        if text:
            provided.append((letters[i], text))
    if len(provided) < 2:
        raise QuestionError("at least two non-empty option columns (option_a, option_b, ...) are required")

    correct_raw = (row.get("correct") or "").strip().upper()
    if not correct_raw:
        raise QuestionError("'correct' is required (e.g. 'B' or 'A,C')")
    correct_labels = {label.strip() for label in correct_raw.split(",") if label.strip()}
    valid_labels = {label for label, _ in provided}
    unknown = correct_labels - valid_labels
    if unknown:
        raise QuestionError(f"'correct' references option(s) that were never provided: {sorted(unknown)}")
    if question_type == "single_choice" and len(correct_labels) != 1:
        raise QuestionError("single_choice requires exactly one correct option in 'correct'")

    return [
        {"label": label, "content": {"text": text}, "is_correct": label in correct_labels, "order": order}
        for order, (label, text) in enumerate(provided, start=1)
    ]


def _bulk_import_true_false_options(row: dict) -> list[dict]:
    correct_raw = (row.get("correct") or "").strip().lower()
    if correct_raw not in ("true", "false"):
        raise QuestionError("'correct' must be 'true' or 'false' for a true_false question")
    return [
        {"label": "true", "content": {}, "is_correct": correct_raw == "true", "order": 1},
        {"label": "false", "content": {}, "is_correct": correct_raw == "false", "order": 2},
    ]


def _bulk_import_one_row(*, organization, actor, subject, class_level, row: dict) -> Question:
    question_type = (row.get("question_type") or "single_choice").strip().lower()
    if question_type not in _BULK_IMPORT_QUESTION_TYPES:
        raise QuestionError(
            f"unsupported question_type for bulk import: {question_type!r} "
            f"(must be one of {sorted(_BULK_IMPORT_QUESTION_TYPES)})"
        )

    text = (row.get("text") or "").strip()
    if not text:
        raise QuestionError("'text' (the question stem) is required")

    topic = None
    topic_name = (row.get("topic") or "").strip()
    if topic_name:
        topic = Topic.objects.filter(subject=subject, name__iexact=topic_name).first()
        if topic is None:
            raise QuestionError(f"unknown topic: {topic_name!r}")

    difficulty = (row.get("difficulty") or "medium").strip().lower()
    if difficulty not in _DIFFICULTY_CODES:
        raise QuestionError(f"invalid difficulty: {difficulty!r} (must be one of {sorted(_DIFFICULTY_CODES)})")

    try:
        marks = Decimal(str(row.get("marks") or "1"))
        negative_marks = Decimal(str(row.get("negative_marks") or "0"))
    except InvalidOperation as exc:
        raise QuestionError(f"marks/negative_marks must be numbers: {exc}") from exc

    options = (
        _bulk_import_true_false_options(row)
        if question_type == "true_false"
        else _bulk_import_choice_options(row, question_type)
    )

    return create_question(
        organization=organization,
        actor=actor,
        subject=subject,
        class_level=class_level,
        topic=topic,
        question_type=question_type,
        difficulty=difficulty,
        marks=marks,
        negative_marks=negative_marks,
        blocks=[{"block_type": "paragraph", "content": {"html": text}, "order": 1}],
        options=options,
    )


def bulk_import_questions(*, organization, actor, subject, class_level, rows: list[dict]) -> dict:
    """Creates one Question per row of a parsed CSV (columns:
    question_type, topic, difficulty, marks, negative_marks, text,
    option_a..option_f, correct — see _bulk_import_one_row). Never aborts
    the whole batch on one bad row: collects a per-row error and keeps
    going, so a single typo in a 200-row sheet doesn't block the other
    199. Returns {"created": [Question, ...], "errors": [{"row": int, "error": str}, ...]}
    (row numbers are 1-based and count the header as row 0's data, i.e.
    the first data row is row 1).
    """
    created = []
    errors = []
    for row_number, row in enumerate(rows, start=1):
        try:
            created.append(
                _bulk_import_one_row(organization=organization, actor=actor, subject=subject, class_level=class_level, row=row)
            )
        except QuestionError as exc:
            errors.append({"row": row_number, "error": str(exc)})
    return {"created": created, "errors": errors}
