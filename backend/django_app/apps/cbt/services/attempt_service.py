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

from apps.cbt.models import (
    ATTEMPT_STATUS_TRANSITIONS,
    AUTO_GRADABLE_QUESTION_TYPES,
    ExamAttempt,
    ExamAttemptEvent,
    StudentAnswer,
)
from apps.cbt.services import scoring_service
from apps.cbt.services.scoring_service import ScoringError

# Of EVENT_TYPE_CHOICES, these are the ones that actually indicate the
# candidate may have left the exam surface to seek outside help — the
# paired "back to normal" events (tab_visible, fullscreen_enter,
# window_focus, reconnect) are informational only and never count here.
SUSPICIOUS_EVENT_TYPES = {"tab_hidden", "fullscreen_exit", "window_blur", "copy_attempt", "paste_attempt"}
# A reasonable default, not a tuned constant: three suspicious signals in
# one attempt is enough to be worth a human's attention, not so few that
# a single accidental Alt-Tab flags everyone.
AUTO_FLAG_THRESHOLD = 3

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
    # Lock the candidacy before checking/creating its OneToOne attempt. Two
    # simultaneous start requests now serialize on the same stable parent row.
    with transaction.atomic():
        candidate = candidate.__class__.objects.select_for_update().select_related("exam").get(pk=candidate.pk)
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
                pass
            elif attempt.status == "in_progress":
                return attempt
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
                    continue
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
        attempt.save(update_fields=[
            "status", "started_at", "expires_at", "question_order", "option_orders",
            "ip_address", "user_agent",
        ])
        return attempt

def heartbeat(*, attempt: ExamAttempt) -> ExamAttempt:
    """Use the server clock and a row lock to expire an attempt once its
    fixed deadline has been reached. Re-reading under the lock prevents a
    stale heartbeat from closing an attempt that another request already
    submitted.
    """
    if attempt.status == "in_progress":
        attempt = _auto_close(attempt=attempt, new_status="expired")
    return attempt


def _auto_close(*, attempt: ExamAttempt, new_status: str) -> ExamAttempt:
    # Commit the terminal state and automatic marks before attempting the
    # separate Result integration. A Result configuration failure must not
    # undo the candidate's submission/expiry or discard their answers.
    with transaction.atomic():
        locked = ExamAttempt.objects.select_for_update().get(pk=attempt.pk)
        if locked.status != "in_progress":
            return locked
        now = timezone.now()
        if locked.expires_at is None or now < locked.expires_at:
            return locked
        _grade_auto_gradable_answers(attempt=locked)
        _transition(attempt=locked, new_status=new_status)
        locked.submitted_at = now
        locked.save(update_fields=["status", "submitted_at"])
        recompute_score(attempt=locked)

    if is_fully_graded(attempt=locked):
        finalize_attempt(attempt=locked, actor=None)
    return locked


def _require_open(attempt: ExamAttempt) -> None:
    if attempt.status != "in_progress":
        raise AttemptError(f"attempt is not in progress (status: {attempt.status!r})")
    if attempt.expires_at is None:
        raise AttemptError("this attempt has no server expiry deadline")
    if timezone.now() >= attempt.expires_at:
        raise AttemptError("time has expired for this attempt")


def save_answer(*, attempt: ExamAttempt, exam_question, response: dict, time_spent_seconds: int = 0) -> StudentAnswer:
    # Serialize answer writes with submit/expiry and with other writes to the
    # same attempt. The unique (attempt, exam_question) constraint remains the
    # final database-level defence against duplicate rows.
    with transaction.atomic():
        locked = ExamAttempt.objects.select_for_update().get(pk=attempt.pk)
        _require_open(locked)
        if exam_question.exam_id != locked.exam_id:
            raise AttemptError("that question does not belong to this attempt's exam")
        answer, _ = StudentAnswer.objects.update_or_create(
            attempt=locked,
            exam_question=exam_question,
            defaults={
                "organization": locked.organization,
                "response": response,
                "time_spent_seconds": time_spent_seconds,
            },
        )
        return answer

def set_flag(*, attempt: ExamAttempt, exam_question, flagged: bool) -> StudentAnswer:
    with transaction.atomic():
        locked = ExamAttempt.objects.select_for_update().get(pk=attempt.pk)
        _require_open(locked)
        if exam_question.exam_id != locked.exam_id:
            raise AttemptError("that question does not belong to this attempt's exam")
        answer, _ = StudentAnswer.objects.get_or_create(
            attempt=locked, exam_question=exam_question,
            defaults={"organization": locked.organization},
        )
        if answer.flagged != flagged:
            answer.flagged = flagged
            answer.save(update_fields=["flagged"])
        return answer

def log_attempt_event(
    *,
    attempt: ExamAttempt,
    event_type: str,
    metadata: dict | None = None,
    client_event_id=None,
) -> ExamAttemptEvent:
    """Append a client-reported signal under the attempt lock.

    A stable client_event_id makes network retries idempotent. Reusing the
    same key with a different event payload is rejected rather than silently
    rewriting the original evidence. Events without a key remain supported
    for older clients but cannot be deduplicated across retries.
    """
    metadata = metadata or {}
    with transaction.atomic():
        locked = ExamAttempt.objects.select_for_update().get(pk=attempt.pk)

        if client_event_id is not None:
            existing = ExamAttemptEvent.objects.filter(
                attempt=locked, client_event_id=client_event_id
            ).first()
            if existing is not None:
                if existing.event_type != event_type or existing.metadata != metadata:
                    raise AttemptError("client_event_id was already used for a different event payload")
                existing._was_created = False
                return existing

        # Replays may be acknowledged after submission, but new evidence
        # must never be appended to a terminal attempt.
        _require_open(locked)

        event = ExamAttemptEvent.objects.create(
            organization=locked.organization,
            attempt=locked,
            event_type=event_type,
            client_event_id=client_event_id,
            metadata=metadata,
        )
        event._was_created = True
        if event_type in SUSPICIOUS_EVENT_TYPES and not locked.flagged_for_review:
            suspicious_count = locked.events.filter(event_type__in=SUSPICIOUS_EVENT_TYPES).count()
            if suspicious_count >= AUTO_FLAG_THRESHOLD:
                locked.flagged_for_review = True
                locked.save(update_fields=["flagged_for_review"])
        return event

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
    """Submit against the persisted server deadline, not a possibly stale
    in-memory attempt or client clock. The row lock serializes manual submit
    with heartbeat/auto-expiry. Submission/expiry and grading commit before
    the separate Result integration, so a Result failure cannot discard
    candidate work.
    """
    with transaction.atomic():
        locked = ExamAttempt.objects.select_for_update().get(pk=attempt.pk)
        if locked.status != "in_progress":
            raise InvalidAttemptTransition(f"cannot submit a {locked.status!r} attempt")
        now = timezone.now()
        if locked.expires_at is None:
            raise AttemptError("this attempt has no server expiry deadline")
        terminal_status = "expired" if now >= locked.expires_at else "submitted"
        _grade_auto_gradable_answers(attempt=locked)
        _transition(attempt=locked, new_status=terminal_status)
        locked.submitted_at = now
        locked.save(update_fields=["status", "submitted_at"])
        recompute_score(attempt=locked)

    if is_fully_graded(attempt=locked):
        finalize_attempt(attempt=locked, actor=actor)
    return locked


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
    # Negative marking may reduce the raw sum below zero, but a
    # candidate's final examination score cannot be negative.
    total_awarded = max(total_awarded, Decimal("0"))
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
    # Lock attempt first (the same lock order used by answer writes and
    # submission), then the answer. This prevents duplicate graders from
    # racing score recomputation/finalization.
    with transaction.atomic():
        attempt = ExamAttempt.objects.select_for_update().get(pk=student_answer.attempt_id)
        answer = StudentAnswer.objects.select_for_update().select_related("exam_question").get(pk=student_answer.pk)
        if attempt.status != "submitted":
            raise AttemptError("cannot grade an answer before the attempt is submitted")
        if answer.graded_at is not None:
            raise AttemptError("this answer has already been graded")
        exam_question = answer.exam_question
        question_type = exam_question.snapshot.get("question_type") if exam_question.snapshot else None
        if question_type in AUTO_GRADABLE_QUESTION_TYPES:
            raise AttemptError(f"{question_type!r} is auto-graded, not manually gradable")
        if marks_awarded < 0 or marks_awarded > exam_question.marks:
            raise AttemptError(f"marks_awarded must be between zero and this question's {exam_question.marks} marks")

        answer.marks_awarded = marks_awarded
        answer.graded_at = timezone.now()
        answer.save(update_fields=["marks_awarded", "graded_at"])
        recompute_score(attempt=attempt)
        should_finalize = is_fully_graded(attempt=attempt)

    if should_finalize:
        finalize_attempt(attempt=attempt, actor=actor)
    return answer

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
    """Idempotently project a terminal CBT attempt into the shared Result
    pipeline. Lock order is attempt -> class-subject -> assessment -> result;
    the assessment lock serializes creation/update even when no Result row
    exists yet, while the database uniqueness constraint remains the final
    duplicate-result guard.
    """
    from apps.academics.models import ClassSubject, Enrollment
    from apps.examinations.models import Assessment, Result
    from apps.examinations.services import result_service

    # Always work from the persisted row. Concurrent finalizers for this
    # attempt serialize here, and retries never trust a stale caller object.
    attempt = (
        ExamAttempt.objects.select_for_update()
        .select_related("exam", "candidate__student")
        .get(pk=attempt.pk)
    )
    if attempt.status not in {"submitted", "expired"}:
        raise AttemptError("only a submitted or expired attempt can be finalized")
    if not is_fully_graded(attempt=attempt):
        raise AttemptError("cannot finalize an attempt with ungraded answers outstanding")

    recompute_score(attempt=attempt)
    exam = attempt.exam
    student = attempt.candidate.student
    attempt.passed = attempt.percentage >= Decimal(str(exam.pass_mark))
    attempt.grade = _resolve_grade(school=exam.school, percentage=attempt.percentage)
    attempt.save(update_fields=["passed", "grade"])

    enrollment = (
        Enrollment.objects.filter(student=student, academic_year=exam.academic_year, status="active")
        .select_related("class_arm")
        .first()
    )
    if enrollment is None:
        raise AttemptError(f"{student} has no active enrollment for {exam.academic_year} — cannot record a result")

    # Lock the stable parent row before get_or_create. This also serializes
    # concurrent finalization of distinct CBT attempts that map to the same
    # class subject/term/name assessment.
    try:
        class_subject = (
            ClassSubject.objects.select_for_update()
            .get(class_arm=enrollment.class_arm, subject=exam.subject)
        )
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
    assessment = Assessment.objects.select_for_update().get(pk=assessment.pk)

    # The assessment lock makes the absent-row case safe: all CBT finalizers
    # for this assessment acquire the same lock before checking or inserting.
    existing = Result.objects.select_for_update().filter(
        assessment=assessment, student=student
    ).first()
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
