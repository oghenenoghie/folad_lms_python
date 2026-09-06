"""Thin views, fat services (§11 ARCHITECTURE.md). Owns exam delivery: the
server-authoritative timer (`expires_at` is fixed once at start_attempt and
never recomputed from a client value — see §16/§35 of the CBT spec),
saving/flagging answers, submission, auto-grading, and — once every
question that needs a human mark has one — finalizing the attempt into the
existing apps.examinations Result/report-card pipeline. Never a competing
result engine: finalize_attempt calls the exact same result_service
enter_result/update_result functions the ordinary (non-CBT) result-entry
path already uses.
"""
import random
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.cbt.models import ATTEMPT_STATUS_TRANSITIONS, AUTO_GRADABLE_QUESTION_TYPES, ExamAttempt, StudentAnswer
from apps.cbt.services import scoring_service
from apps.cbt.services.scoring_service import ScoringError

# CBTExam.exam_type has no 1:1 counterpart in apps.examinations.Assessment's
# ASSESSMENT_TYPE_CHOICES (test/quiz/assignment/project/practical/exam) —
# this is a deliberate, reasonable mapping, not a missing feature.
_ASSESSMENT_TYPE_BY_EXAM_TYPE = {
    "ca": "test",
    "test": "test",
    "quiz": "quiz",
    "midterm": "test",
    "terminal": "exam",
    "mock": "exam",
    "entrance": "exam",
    "promotion": "exam",
}


class AttemptError(ValueError):
    """A validation failure the caller should surface as a 4xx, not a bug."""


class InvalidAttemptTransition(AttemptError):
    pass


def _transition(*, attempt: ExamAttempt, new_status: str) -> None:
    allowed = ATTEMPT_STATUS_TRANSITIONS.get(attempt.status, set())
    if new_status not in allowed:
        raise InvalidAttemptTransition(f"cannot move a {attempt.status!r} attempt to {new_status!r}")
    attempt.status = new_status


def start_attempt(*, candidate, ip_address: str = "", user_agent: str = "") -> ExamAttempt:
    exam = candidate.exam
    if exam.status != "published":
        raise AttemptError(f"exam is not open for attempts (status: {exam.status!r})")
    if not candidate.is_eligible:
        raise AttemptError("candidate is not eligible for this exam")
    now = timezone.now()
    if now < exam.start_at:
        raise AttemptError("exam has not opened yet")
    if now > exam.end_at:
        raise AttemptError("exam window has closed")

    attempt, created = ExamAttempt.objects.get_or_create(
        candidate=candidate, defaults={"organization": exam.organization, "exam": exam}
    )
    if not created:
        if attempt.status == "not_started":
            pass  # fall through and start it below (e.g. a prior get_or_create race)
        elif attempt.status == "in_progress":
            return attempt  # resume — question_order/expires_at already fixed
        else:
            raise AttemptError(f"this attempt is already {attempt.status} and cannot be restarted")

    exam_questions = list(exam.exam_questions.order_by("order"))
    order = [str(eq.public_id) for eq in exam_questions]
    if exam.randomize_questions:
        random.shuffle(order)

    option_orders: dict[str, list[str]] = {}
    if exam.randomize_options:
        for eq in exam_questions:
            snapshot = eq.snapshot
            if not snapshot or snapshot["question_type"] in _ANSWER_KEY_IN_OPTIONS_TYPES:
                continue  # nothing on-screen to shuffle — see that set's docstring
            labels = [o["label"] for o in snapshot["options"]]
            if len(labels) > 1:
                random.shuffle(labels)
                option_orders[str(eq.public_id)] = labels

    _transition(attempt=attempt, new_status="in_progress")
    attempt.started_at = now
    attempt.expires_at = now + timezone.timedelta(
        minutes=exam.duration_minutes + candidate.extra_time_minutes
    )
    attempt.question_order = order
    attempt.option_orders = option_orders
    attempt.ip_address = ip_address or None
    attempt.user_agent = user_agent
    attempt.save(
        update_fields=[
            "status", "started_at", "expires_at", "question_order", "option_orders",
            "ip_address", "user_agent",
        ]
    )
    return attempt


def heartbeat(*, attempt: ExamAttempt) -> ExamAttempt:
    """The server clock is the only clock that matters — a client checks in
    here rather than trusting its own countdown, and gets auto-submitted
    the moment it's overrun its expiry, whether or not it ever calls
    submit_attempt itself.
    """
    if attempt.status == "in_progress" and timezone.now() >= attempt.expires_at:
        _auto_close(attempt=attempt, new_status="expired")
    return attempt


def _auto_close(*, attempt: ExamAttempt, new_status: str) -> ExamAttempt:
    _grade_auto_gradable_answers(attempt=attempt)
    _transition(attempt=attempt, new_status=new_status)
    attempt.submitted_at = timezone.now()
    attempt.save(update_fields=["status", "submitted_at"])
    recompute_score(attempt=attempt)
    if is_fully_graded(attempt=attempt):
        finalize_attempt(attempt=attempt, actor=None)
    return attempt


def _require_open(attempt: ExamAttempt) -> None:
    if attempt.status != "in_progress":
        raise AttemptError(f"attempt is not in progress (status: {attempt.status!r})")
    if timezone.now() >= attempt.expires_at:
        raise AttemptError("time has expired for this attempt")


def save_answer(*, attempt: ExamAttempt, exam_question, response: dict, time_spent_seconds: int = 0) -> StudentAnswer:
    _require_open(attempt)
    if exam_question.exam_id != attempt.exam_id:
        raise AttemptError("that question does not belong to this attempt's exam")
    answer, _ = StudentAnswer.objects.update_or_create(
        attempt=attempt,
        exam_question=exam_question,
        defaults={
            "organization": attempt.organization,
            "response": response,
            "time_spent_seconds": time_spent_seconds,
        },
    )
    return answer


def set_flag(*, attempt: ExamAttempt, exam_question, flagged: bool) -> StudentAnswer:
    _require_open(attempt)
    answer, _ = StudentAnswer.objects.get_or_create(
        attempt=attempt, exam_question=exam_question, defaults={"organization": attempt.organization}
    )
    answer.flagged = flagged
    answer.save(update_fields=["flagged"])
    return answer


def _grade_auto_gradable_answers(*, attempt: ExamAttempt) -> None:
    for answer in attempt.answers.select_related("exam_question").filter(graded_at__isnull=True):
        try:
            is_correct, marks_awarded = scoring_service.grade_response(
                exam_question=answer.exam_question, response=answer.response
            )
        except ScoringError:
            continue  # a subjective type — left ungraded for a human marker
        answer.is_correct = is_correct
        answer.marks_awarded = marks_awarded
        answer.graded_at = timezone.now()
        answer.save(update_fields=["is_correct", "marks_awarded", "graded_at"])


def submit_attempt(*, attempt: ExamAttempt, actor) -> ExamAttempt:
    """Deliberately NOT wrapped in one atomic block together with
    finalize_attempt: a Result-integration failure (e.g. no ClassSubject
    configured yet for this student's class/subject) must never roll back
    — and so silently discard — the submission and scoring that already
    succeeded. finalize_attempt is its own self-contained atomic unit;
    its failure only undoes its own partial writes.
    """
    if attempt.status != "in_progress":
        raise InvalidAttemptTransition(f"cannot submit a {attempt.status!r} attempt")
    _grade_auto_gradable_answers(attempt=attempt)
    _transition(attempt=attempt, new_status="submitted")
    attempt.submitted_at = timezone.now()
    attempt.save(update_fields=["status", "submitted_at"])
    recompute_score(attempt=attempt)
    if is_fully_graded(attempt=attempt):
        finalize_attempt(attempt=attempt, actor=actor)
    return attempt


# These four types keep their entire answer key inside options[0].content
# (see scoring_service._grade_numeric/_grade_matching/_grade_ordering/
# _grade_hotspot) rather than flagging a chosen option is_correct — so for
# delivery to a candidate mid-attempt, the whole `options` list must be
# dropped, not just the is_correct/explanation fields.
_ANSWER_KEY_IN_OPTIONS_TYPES = {"numeric", "matching", "ordering", "hotspot"}


def sanitize_snapshot_for_delivery(snapshot: dict) -> dict:
    """Strips everything a candidate must never see while an attempt is
    still `in_progress`: which option is_correct, a grader's explanation,
    and — for the types whose answer key lives inside an option's content —
    the options entirely.
    """
    question_type = snapshot["question_type"]
    if question_type in _ANSWER_KEY_IN_OPTIONS_TYPES:
        options = []
    else:
        options = [
            {"label": o["label"], "content": o["content"], "order": o["order"]} for o in snapshot["options"]
        ]
    return {
        "question_type": question_type,
        "difficulty": snapshot["difficulty"],
        "marks": snapshot["marks"],
        "blocks": snapshot["blocks"],
        "options": options,
    }


def _apply_option_order(options: list[dict], label_order: list[str] | None) -> list[dict]:
    """Reorders an already-sanitized options list to match a stored
    label_order (attempt.option_orders[exam_question]) — the display order
    fixed once at start_attempt, never recomputed per request. Falls back
    to the snapshot's own order when no stored order exists (randomize_options
    was off, or this question type has nothing to shuffle).
    """
    if not label_order:
        return options
    by_label = {o["label"]: o for o in options}
    return [by_label[label] for label in label_order if label in by_label]


def build_delivery_payload(*, attempt: ExamAttempt) -> list[dict]:
    """The ordered, answer-key-stripped question content a candidate needs
    to actually take the exam. `attempt.question_order` (fixed once at
    start_attempt) drives both the sequence and which frozen
    ExamQuestion.snapshot each entry uses, and `attempt.option_orders`
    (same fixed-once-at-start rule) drives each question's own option
    display order, so a client can reconstruct the exact same attempt
    after a refresh or reconnect.
    """
    exam_questions = {str(eq.public_id): eq for eq in attempt.exam.exam_questions.all()}
    existing_answers = {a.exam_question_id: a for a in attempt.answers.all()}
    payload = []
    for public_id in attempt.question_order:
        exam_question = exam_questions.get(public_id)
        if exam_question is None:
            continue
        answer = existing_answers.get(exam_question.id)
        sanitized = sanitize_snapshot_for_delivery(exam_question.snapshot)
        sanitized["options"] = _apply_option_order(sanitized["options"], attempt.option_orders.get(public_id))
        payload.append(
            {
                "exam_question": public_id,
                "marks": str(exam_question.marks),
                "snapshot": sanitized,
                "response": answer.response if answer else None,
                "flagged": answer.flagged if answer else False,
            }
        )
    return payload


def recompute_score(*, attempt: ExamAttempt) -> ExamAttempt:
    total_awarded = attempt.answers.filter(graded_at__isnull=False).aggregate(total=Sum("marks_awarded"))[
        "total"
    ] or Decimal("0")
    attempt.score = total_awarded
    attempt.percentage = (
        round((total_awarded / attempt.exam.total_marks) * 100, 2) if attempt.exam.total_marks else Decimal("0")
    )
    attempt.save(update_fields=["score", "percentage"])
    return attempt


def is_fully_graded(*, attempt: ExamAttempt) -> bool:
    """True once nothing the student actually answered is still awaiting a
    mark — an unanswered subjective question has no StudentAnswer row at
    all, so it never blocks finalization (nothing to grade).
    """
    return not attempt.answers.filter(graded_at__isnull=True).exists()


def grade_subjective_answer(*, student_answer: StudentAnswer, marks_awarded: Decimal, actor) -> StudentAnswer:
    exam_question = student_answer.exam_question
    if student_answer.attempt.status != "submitted":
        raise AttemptError("cannot grade an answer before the attempt is submitted")
    question_type = exam_question.snapshot.get("question_type") if exam_question.snapshot else None
    if question_type in AUTO_GRADABLE_QUESTION_TYPES:
        raise AttemptError(f"{question_type!r} is auto-graded, not manually gradable")
    if marks_awarded > exam_question.marks:
        raise AttemptError(f"marks_awarded cannot exceed this question's {exam_question.marks} marks")

    student_answer.marks_awarded = marks_awarded
    student_answer.graded_at = timezone.now()
    student_answer.save(update_fields=["marks_awarded", "graded_at"])

    attempt = student_answer.attempt
    recompute_score(attempt=attempt)
    if is_fully_graded(attempt=attempt):
        finalize_attempt(attempt=attempt, actor=actor)
    return student_answer


def _resolve_grade(*, school, percentage) -> str:
    from apps.examinations.models import GradeBand

    band = (
        GradeBand.objects.filter(
            grading_scheme__school=school,
            grading_scheme__is_default=True,
            min_score__lte=percentage,
            max_score__gte=percentage,
        )
        .order_by("-min_score")
        .first()
    )
    return band.grade if band else ""


@transaction.atomic
def finalize_attempt(*, attempt: ExamAttempt, actor) -> ExamAttempt:
    """The point at which a CBT attempt's score becomes an
    apps.examinations Result, exactly the same way any other
    assessment's score does — through result_service, never a parallel
    result path. Requires every answered question to already have a mark
    (see is_fully_graded); callers only ever reach this once that's true.
    """
    from apps.academics.models import ClassSubject, Enrollment
    from apps.examinations.models import Assessment, Result
    from apps.examinations.services import result_service

    if not is_fully_graded(attempt=attempt):
        raise AttemptError("cannot finalize an attempt with ungraded answers outstanding")

    recompute_score(attempt=attempt)
    exam = attempt.exam
    student = attempt.candidate.student

    # exam.pass_mark can still be a plain str in memory on an object that
    # was just created/mutated in this same process without a DB round
    # trip (Django doesn't coerce a DecimalField's Python value until it's
    # (re)loaded from the database) — coerce explicitly rather than
    # depending on the caller having a freshly-fetched instance.
    attempt.passed = attempt.score >= Decimal(str(exam.pass_mark))
    attempt.grade = _resolve_grade(school=exam.school, percentage=attempt.percentage)
    attempt.save(update_fields=["passed", "grade"])

    enrollment = (
        Enrollment.objects.filter(student=student, academic_year=exam.academic_year, status="active")
        .select_related("class_arm")
        .first()
    )
    if enrollment is None:
        raise AttemptError(f"{student} has no active enrollment for {exam.academic_year} — cannot record a result")
    try:
        class_subject = ClassSubject.objects.get(class_arm=enrollment.class_arm, subject=exam.subject)
    except ClassSubject.DoesNotExist as exc:
        raise AttemptError(
            f"no teacher is assigned to {exam.subject} for {enrollment.class_arm} — configure that "
            "class-subject assignment before this attempt's result can be recorded"
        ) from exc

    assessment, _ = Assessment.objects.get_or_create(
        class_subject=class_subject,
        term=exam.term,
        name=exam.name,
        defaults={
            "organization": exam.organization,
            "assessment_type": _ASSESSMENT_TYPE_BY_EXAM_TYPE.get(exam.exam_type, "test"),
            "score_category": "cbt",
            "weight": Decimal("100.00"),
            "max_score": exam.total_marks,
        },
    )

    existing = Result.objects.filter(assessment=assessment, student=student).first()
    if existing is None:
        result_service.enter_result(assessment=assessment, student=student, actor=actor, score=attempt.score)
    elif existing.status == "entered":
        result_service.update_result(result=existing, actor=actor, score=attempt.score)
    else:
        raise AttemptError(
            f"a result for {student} on {assessment} already exists past the 'entered' stage "
            f"(status: {existing.status!r}) — an administrator must reconcile it manually"
        )
    return attempt
