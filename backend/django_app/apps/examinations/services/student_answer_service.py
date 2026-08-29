"""Thin views, fat services (§11 ARCHITECTURE.md). `submit_answer` auto-grades
objective question types (multiple_choice/true_false) from the
QuestionOption marked `is_correct` at submission time; subjective types
(short_answer/essay) are left ungraded until a teacher calls
`grade_answer`. `finalize_assessment_score` sums a student's graded
answers for an Assessment and writes the total into their Result via the
existing result_service functions, rather than duplicating the
enter/update/workflow logic already there.
"""
from decimal import Decimal

from django.utils import timezone

from apps.examinations.models import (
    OBJECTIVE_QUESTION_TYPES,
    Assessment,
    Question,
    QuestionOption,
    Result,
    StudentAnswer,
)
from apps.examinations.services import result_service
from apps.students.models import Student


class InvalidAnswer(Exception):
    pass


def submit_answer(
    *,
    question: Question,
    student: Student,
    actor,
    selected_option: QuestionOption | None = None,
    text_answer: str = "",
) -> StudentAnswer:
    is_correct = None
    marks_awarded = None
    if question.question_type in OBJECTIVE_QUESTION_TYPES:
        if selected_option is None or selected_option.question_id != question.id:
            raise InvalidAnswer("an objective question requires a selected_option on that question")
        is_correct = selected_option.is_correct
        marks_awarded = question.marks if is_correct else Decimal("0.00")
    else:
        if not text_answer.strip():
            raise InvalidAnswer("a subjective question requires a non-blank text_answer")
        selected_option = None

    return StudentAnswer.objects.create(
        organization=question.organization,
        question=question,
        student=student,
        selected_option=selected_option,
        text_answer=text_answer,
        is_correct=is_correct,
        marks_awarded=marks_awarded,
        submitted_at=timezone.now(),
        created_by=actor,
        updated_by=actor,
    )


def grade_answer(
    *, answer: StudentAnswer, actor, marks_awarded: Decimal, is_correct: bool | None = None
) -> StudentAnswer:
    if answer.question.question_type in OBJECTIVE_QUESTION_TYPES:
        raise InvalidAnswer("objective question answers are graded automatically at submission time")
    answer.marks_awarded = marks_awarded
    answer.is_correct = is_correct
    answer.updated_by = actor
    answer.save(update_fields=["marks_awarded", "is_correct", "updated_by", "updated_at"])
    return answer


def delete_answer(*, answer: StudentAnswer, actor) -> None:
    answer.deleted_at = timezone.now()
    answer.updated_by = actor
    answer.save(update_fields=["deleted_at", "updated_by", "updated_at"])


def finalize_assessment_score(*, assessment: Assessment, student: Student, actor) -> Result:
    answers = StudentAnswer.objects.filter(question__assessment=assessment, student=student)
    if not answers.exists():
        raise InvalidAnswer("student has no answers recorded for this assessment")
    if answers.filter(marks_awarded__isnull=True).exists():
        raise InvalidAnswer("cannot finalize score while ungraded subjective answers remain")

    total = sum((a.marks_awarded for a in answers), Decimal("0.00"))
    existing = Result.objects.filter(assessment=assessment, student=student).first()
    if existing:
        return result_service.update_result(result=existing, actor=actor, score=total)
    return result_service.enter_result(assessment=assessment, student=student, actor=actor, score=total)
