"""Thin views, fat services (§11 ARCHITECTURE.md). Owns exam authoring
(create/update/delete while draft), candidate assignment, question
selection (manual add or bank-driven generation), and publishing — the
point at which every ExamQuestion gets an immutable content snapshot (see
question_service.build_question_snapshot) and total_marks is derived from
what the exam actually contains, never hand-entered.
"""
import random
from decimal import Decimal

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.cbt.models import (
    EXAM_ELIGIBLE_QUESTION_STATUSES,
    EXAM_STATUS_TRANSITIONS,
    CBTExam,
    ExamCandidate,
    ExamQuestion,
    ExamSection,
    Question,
)
from apps.cbt.services import question_service


class ExamError(ValueError):
    """A validation failure the caller should surface as a 4xx, not a bug."""


class InvalidExamTransition(ExamError):
    pass


def _require_draft(exam: CBTExam, action: str) -> None:
    if exam.status != "draft":
        raise ExamError(f"cannot {action} a {exam.status!r} exam")


def _require_not_archived(exam: CBTExam, action: str) -> None:
    if exam.status == "archived":
        raise ExamError(f"cannot {action} an archived exam")


def create_exam(*, organization, actor, **fields) -> CBTExam:
    return CBTExam.objects.create(organization=organization, created_by=actor, updated_by=actor, **fields)


def update_exam(*, exam: CBTExam, actor, **fields) -> CBTExam:
    _require_draft(exam, "edit")
    for field, value in fields.items():
        setattr(exam, field, value)
    exam.updated_by = actor
    update_fields = [*fields.keys(), "updated_by", "updated_at"] if fields else ["updated_by", "updated_at"]
    exam.save(update_fields=update_fields)
    return exam


def delete_exam(*, exam: CBTExam, actor) -> None:
    _require_draft(exam, "delete")
    exam.deleted_at = timezone.now()
    exam.updated_by = actor
    exam.save(update_fields=["deleted_at", "updated_by", "updated_at"])


def add_question_to_exam(
    *, exam: CBTExam, question: Question, section=None, order: int | None = None, marks_override=None
) -> ExamQuestion:
    _require_draft(exam, "add questions to")
    if question.status not in EXAM_ELIGIBLE_QUESTION_STATUSES:
        raise ExamError(f"question {question.code} is not approved for exam use (status: {question.status!r})")
    if order is None:
        last = exam.exam_questions.order_by("-order").first()
        order = (last.order + 1) if last else 1
    return ExamQuestion.objects.create(
        organization=exam.organization,
        exam=exam,
        question=question,
        section=section,
        order=order,
        marks_override=marks_override,
    )


def remove_question_from_exam(*, exam_question: ExamQuestion) -> None:
    _require_draft(exam_question.exam, "remove questions from")
    exam_question.delete()


def reorder_exam_questions(*, exam: CBTExam, ordered_public_ids: list[str]) -> None:
    _require_draft(exam, "reorder questions on")
    lookup = {str(eq.public_id): eq for eq in exam.exam_questions.all()}
    if set(lookup) != set(ordered_public_ids):
        raise ExamError("ordered_public_ids must include every question currently on this exam, exactly once")
    with transaction.atomic():
        # Bump every row out of range first — reassigning in one pass could
        # transiently collide with the (exam, order) unique constraint
        # (e.g. swapping #1 and #2) since Postgres checks it per-statement.
        offset = len(lookup) + 1000
        for exam_question in lookup.values():
            exam_question.order += offset
            exam_question.save(update_fields=["order"])
        for index, public_id in enumerate(ordered_public_ids, start=1):
            exam_question = lookup[public_id]
            exam_question.order = index
            exam_question.save(update_fields=["order"])


def generate_questions_for_exam(
    *,
    exam: CBTExam,
    subject,
    class_level,
    count: int,
    topic=None,
    difficulty_distribution: dict[str, int] | None = None,
    question_types: list[str] | None = None,
) -> list[ExamQuestion]:
    """Auto-selects `count` eligible bank questions (matching subject/
    class_level/topic/question_types, and not already on this exam) and
    adds them to the exam. `difficulty_distribution` is a weight per
    difficulty (e.g. {"easy": 30, "medium": 50, "hard": 20}) — weights are
    proportions, not exact counts, and the last difficulty absorbs any
    rounding remainder so the total always equals `count` exactly (or
    fewer, if the bank doesn't have enough eligible questions).
    """
    _require_draft(exam, "add questions to")

    base_qs = Question.objects.filter(
        subject=subject, class_level=class_level, status__in=EXAM_ELIGIBLE_QUESTION_STATUSES, deleted_at__isnull=True,
    ).exclude(exam_questions__exam=exam)
    if topic is not None:
        base_qs = base_qs.filter(topic=topic)
    if question_types:
        base_qs = base_qs.filter(question_type__in=question_types)

    selected: list[Question] = []
    if difficulty_distribution:
        total_weight = sum(difficulty_distribution.values())
        difficulties = list(difficulty_distribution.items())
        remaining = count
        for index, (difficulty, weight) in enumerate(difficulties):
            is_last = index == len(difficulties) - 1
            share = remaining if is_last else round(count * weight / total_weight)
            pool = list(base_qs.filter(difficulty=difficulty).exclude(pk__in=[q.pk for q in selected]))
            take = min(share, len(pool))
            selected.extend(random.sample(pool, take))
            remaining -= take
    else:
        pool = list(base_qs)
        selected = random.sample(pool, min(count, len(pool)))

    if not selected:
        raise ExamError("no eligible questions matched the given criteria")

    next_order = exam.exam_questions.aggregate(Max("order"))["order__max"] or 0
    created = [
        ExamQuestion.objects.create(
            organization=exam.organization, exam=exam, question=question, order=next_order + offset
        )
        for offset, question in enumerate(selected, start=1)
    ]
    return created


def add_section(*, exam: CBTExam, name: str, order: int | None = None, **fields) -> ExamSection:
    _require_draft(exam, "add sections to")
    if order is None:
        last = exam.sections.order_by("-order").first()
        order = (last.order + 1) if last else 1
    return ExamSection.objects.create(organization=exam.organization, exam=exam, name=name, order=order, **fields)


def update_section(*, section: ExamSection, **fields) -> ExamSection:
    _require_draft(section.exam, "edit sections on")
    for field, value in fields.items():
        setattr(section, field, value)
    if fields:
        section.save(update_fields=list(fields.keys()))
    return section


def remove_section(*, section: ExamSection) -> None:
    _require_draft(section.exam, "remove sections from")
    section.delete()


def update_exam_question(*, exam_question: ExamQuestion, **fields) -> ExamQuestion:
    _require_draft(exam_question.exam, "edit questions on")
    for field, value in fields.items():
        setattr(exam_question, field, value)
    if fields:
        exam_question.save(update_fields=list(fields.keys()))
    return exam_question


def add_candidate(*, exam: CBTExam, student) -> ExamCandidate:
    _require_not_archived(exam, "add candidates to")
    return ExamCandidate.objects.create(organization=exam.organization, exam=exam, student=student)


def add_candidates_from_class_arm(*, exam: CBTExam, class_arm, academic_year) -> list[ExamCandidate]:
    """Every actively-enrolled student in `class_arm` for `academic_year`
    becomes a candidate — get_or_create so calling this twice (e.g. after
    a late enrollment) never duplicates an existing candidacy.
    """
    from apps.academics.models import Enrollment

    _require_not_archived(exam, "add candidates to")
    enrollments = Enrollment.objects.filter(
        class_arm=class_arm, academic_year=academic_year, status="active"
    ).select_related("student")
    candidates = []
    for enrollment in enrollments:
        candidate, _ = ExamCandidate.objects.get_or_create(
            exam=exam, student=enrollment.student, defaults={"organization": exam.organization}
        )
        candidates.append(candidate)
    return candidates


def remove_candidate(*, candidate: ExamCandidate) -> None:
    _require_not_archived(candidate.exam, "remove candidates from")
    candidate.delete()


def update_candidate(*, candidate: ExamCandidate, **fields) -> ExamCandidate:
    _require_not_archived(candidate.exam, "edit candidates on")
    for field, value in fields.items():
        setattr(candidate, field, value)
    if fields:
        candidate.save(update_fields=list(fields.keys()))
    return candidate


@transaction.atomic
def publish_exam(*, exam: CBTExam, actor) -> CBTExam:
    if exam.status not in EXAM_STATUS_TRANSITIONS or "published" not in EXAM_STATUS_TRANSITIONS[exam.status]:
        raise InvalidExamTransition(f"cannot publish a {exam.status!r} exam")
    if not exam.exam_questions.exists():
        raise ExamError("exam has no questions")
    if not exam.candidates.exists():
        raise ExamError("exam has no candidates")
    if exam.start_at >= exam.end_at:
        raise ExamError("start_at must be before end_at")

    total = Decimal("0")
    for exam_question in exam.exam_questions.select_related("question").prefetch_related(
        "question__blocks", "question__options"
    ):
        exam_question.snapshot = question_service.build_question_snapshot(exam_question.question)
        exam_question.save(update_fields=["snapshot"])
        total += exam_question.marks

    exam.total_marks = total
    exam.status = "published"
    exam.published_at = timezone.now()
    exam.updated_by = actor
    exam.save(update_fields=["total_marks", "status", "published_at", "updated_by", "updated_at"])
    return exam


def archive_exam(*, exam: CBTExam, actor) -> CBTExam:
    if exam.status not in EXAM_STATUS_TRANSITIONS or "archived" not in EXAM_STATUS_TRANSITIONS[exam.status]:
        raise InvalidExamTransition(f"cannot archive a {exam.status!r} exam")
    exam.status = "archived"
    exam.updated_by = actor
    exam.save(update_fields=["status", "updated_by", "updated_at"])
    return exam
