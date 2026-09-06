"""apps.cbt Phase 4: exam delivery — start/heartbeat/answer/submit and the
finalize-into-Result pipeline. Builds on Phase 3's exam_service (already
covered by test_cbt_exams.py) to get a published exam with a candidate,
then exercises attempt_service directly, the same way earlier phases
exercised their own service layer before the API existed.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.cbt.models import ExamAttempt, ExamAttemptEvent, QuestionOption, StudentAnswer
from apps.cbt.services.attempt_service import (
    AUTO_FLAG_THRESHOLD,
    AttemptError,
    InvalidAttemptTransition,
    build_delivery_payload,
    finalize_attempt,
    grade_subjective_answer,
    heartbeat,
    is_fully_graded,
    log_attempt_event,
    sanitize_snapshot_for_delivery,
    save_answer,
    set_flag,
    start_attempt,
    submit_attempt,
)
from apps.cbt.services.exam_service import add_candidate, add_question_to_exam, publish_exam
from apps.cbt.services.question_service import approve_question, submit_question
from apps.examinations.models import Assessment, Result


def _single_choice_question(cbt_question_factory, fs, correct_label="B", marks="5.00"):
    question = cbt_question_factory(
        subject=fs["subject"], class_level=fs["class_level"], question_type="single_choice", marks=marks
    )
    QuestionOption.objects.create(
        organization=question.organization, question=question, label="A", content={}, is_correct=(correct_label == "A"), order=1
    )
    QuestionOption.objects.create(
        organization=question.organization, question=question, label="B", content={}, is_correct=(correct_label == "B"), order=2
    )
    submit_question(question=question, actor=None)
    approve_question(question=question, actor=None)
    return question


@pytest.fixture
def ready_exam(cbt_exam_fixture_set, cbt_question_factory, student_factory, staff_factory, teacher_factory, class_subject_factory, enrollment_factory):
    """A published exam, one single_choice question (B is correct, 5
    marks), one eligible candidate whose enrollment/class-subject is
    already configured — the minimal scaffolding an attempt needs to
    reach finalize_attempt successfully.
    """
    fs = cbt_exam_fixture_set
    exam = fs["exam"]
    exam.start_at = timezone.now() - timedelta(minutes=5)
    exam.end_at = timezone.now() + timedelta(hours=1)
    exam.duration_minutes = 30
    # cbt_exam_factory's default pass_mark ("40.00") assumes a bigger exam
    # than this fixture's single 5-mark question — override so a fully
    # correct attempt on this exam actually passes.
    exam.pass_mark = Decimal("3.00")
    exam.save(update_fields=["start_at", "end_at", "duration_minutes", "pass_mark"])

    question = _single_choice_question(cbt_question_factory, fs)
    add_question_to_exam(exam=exam, question=question)

    student = student_factory(school=fs["school"])
    enrollment_factory(student=student, class_arm=fs["class_arm"], academic_year=fs["academic_year"])
    teacher = teacher_factory(staff=staff_factory(school=fs["school"]))
    class_subject_factory(class_arm=fs["class_arm"], subject=fs["subject"], teacher=teacher)

    candidate = add_candidate(exam=exam, student=student)
    published = publish_exam(exam=exam, actor=None)
    return {**fs, "exam": published, "question": question, "student": student, "candidate": candidate}


@pytest.mark.django_db
def test_start_attempt_sets_timer_and_question_order(ready_exam):
    candidate = ready_exam["candidate"]
    attempt = start_attempt(candidate=candidate)

    assert attempt.status == "in_progress"
    assert attempt.started_at is not None
    expected_expiry = attempt.started_at + timedelta(minutes=ready_exam["exam"].duration_minutes)
    assert abs((attempt.expires_at - expected_expiry).total_seconds()) < 1
    assert len(attempt.question_order) == 1


@pytest.mark.django_db
def test_start_attempt_applies_extra_time(ready_exam):
    candidate = ready_exam["candidate"]
    candidate.extra_time_minutes = 15
    candidate.save(update_fields=["extra_time_minutes"])

    attempt = start_attempt(candidate=candidate)
    expected_expiry = attempt.started_at + timedelta(minutes=30 + 15)
    assert abs((attempt.expires_at - expected_expiry).total_seconds()) < 1


@pytest.mark.django_db
def test_start_attempt_is_idempotent_and_resumes(ready_exam):
    candidate = ready_exam["candidate"]
    first = start_attempt(candidate=candidate)
    second = start_attempt(candidate=candidate)

    assert first.pk == second.pk
    assert first.started_at == second.started_at
    assert ExamAttempt.objects.filter(candidate=candidate).count() == 1


@pytest.mark.django_db
def test_start_attempt_rejects_ineligible_candidate(ready_exam):
    candidate = ready_exam["candidate"]
    candidate.is_eligible = False
    candidate.save(update_fields=["is_eligible"])

    with pytest.raises(AttemptError):
        start_attempt(candidate=candidate)


@pytest.mark.django_db
def test_start_attempt_rejects_outside_exam_window(ready_exam):
    exam = ready_exam["exam"]
    exam.end_at = timezone.now() - timedelta(minutes=1)
    exam.save(update_fields=["end_at"])

    with pytest.raises(AttemptError):
        start_attempt(candidate=ready_exam["candidate"])


def test_sanitize_snapshot_strips_answer_key_for_choice_types():
    snapshot = {
        "question_type": "single_choice",
        "difficulty": "easy",
        "marks": "5.00",
        "blocks": [{"block_type": "text", "content": {"text": "2+2?"}, "order": 1}],
        "options": [
            {"label": "A", "content": {"text": "3"}, "is_correct": False, "order": 1, "explanation": "too low"},
            {"label": "B", "content": {"text": "4"}, "is_correct": True, "order": 2, "explanation": "correct"},
        ],
    }
    sanitized = sanitize_snapshot_for_delivery(snapshot)
    assert sanitized["options"] == [
        {"label": "A", "content": {"text": "3"}, "order": 1},
        {"label": "B", "content": {"text": "4"}, "order": 2},
    ]
    assert "is_correct" not in sanitized["options"][0]
    assert "explanation" not in sanitized["options"][0]


def test_sanitize_snapshot_drops_options_entirely_for_answer_key_types():
    for question_type in ("numeric", "matching", "ordering", "hotspot"):
        snapshot = {
            "question_type": question_type,
            "difficulty": "easy",
            "marks": "5.00",
            "blocks": [],
            "options": [{"label": "", "content": {"value": 42, "tolerance": 0.5}, "is_correct": False, "order": 1}],
        }
        assert sanitize_snapshot_for_delivery(snapshot)["options"] == []


@pytest.mark.django_db
def test_start_attempt_randomizes_option_order_by_default(ready_exam):
    # cbt_exam_factory doesn't override randomize_options, so the model's
    # own default (True) applies here.
    candidate = ready_exam["candidate"]
    exam_question = ready_exam["exam"].exam_questions.get()
    attempt = start_attempt(candidate=candidate)

    stored_order = attempt.option_orders[str(exam_question.public_id)]
    assert sorted(stored_order) == ["A", "B"]


@pytest.mark.django_db
def test_delivery_payload_uses_the_stored_option_order_and_never_recomputes_it(ready_exam):
    candidate = ready_exam["candidate"]
    exam_question = ready_exam["exam"].exam_questions.get()
    attempt = start_attempt(candidate=candidate)
    stored_order = attempt.option_orders[str(exam_question.public_id)]

    first = build_delivery_payload(attempt=attempt)
    second = build_delivery_payload(attempt=attempt)
    for payload in (first, second):
        delivered_labels = [o["label"] for o in payload[0]["snapshot"]["options"]]
        assert delivered_labels == stored_order


@pytest.mark.django_db
def test_no_option_randomization_when_exam_disables_it(ready_exam):
    exam = ready_exam["exam"]
    exam.randomize_options = False
    exam.save(update_fields=["randomize_options"])
    exam_question = exam.exam_questions.get()

    attempt = start_attempt(candidate=ready_exam["candidate"])
    assert attempt.option_orders == {}

    payload = build_delivery_payload(attempt=attempt)
    delivered_labels = [o["label"] for o in payload[0]["snapshot"]["options"]]
    assert delivered_labels == ["A", "B"]  # natural QuestionOption.order


@pytest.mark.django_db
def test_answer_key_only_types_never_get_an_option_order(
    cbt_exam_fixture_set, cbt_question_factory, student_factory, enrollment_factory
):
    fs = cbt_exam_fixture_set
    exam = fs["exam"]
    exam.start_at = timezone.now() - timedelta(minutes=5)
    exam.end_at = timezone.now() + timedelta(hours=1)
    exam.save(update_fields=["start_at", "end_at"])

    question = cbt_question_factory(
        subject=fs["subject"], class_level=fs["class_level"], question_type="numeric", marks="5.00"
    )
    from apps.cbt.models import QuestionOption as _QuestionOption

    _QuestionOption.objects.create(
        organization=question.organization, question=question, label="", content={"value": 42, "tolerance": 0.5}, order=1
    )
    submit_question(question=question, actor=None)
    approve_question(question=question, actor=None)
    add_question_to_exam(exam=exam, question=question)

    student = student_factory(school=fs["school"])
    enrollment_factory(student=student, class_arm=fs["class_arm"], academic_year=fs["academic_year"])
    candidate = add_candidate(exam=exam, student=student)
    published = publish_exam(exam=exam, actor=None)

    attempt = start_attempt(candidate=candidate)
    assert attempt.option_orders == {}

    payload = build_delivery_payload(attempt=attempt)
    assert payload[0]["snapshot"]["options"] == []


@pytest.mark.django_db
def test_build_delivery_payload_follows_question_order_and_includes_existing_answer(ready_exam):
    candidate = ready_exam["candidate"]
    exam_question = ready_exam["exam"].exam_questions.get()
    attempt = start_attempt(candidate=candidate)
    save_answer(attempt=attempt, exam_question=exam_question, response={"selected_option_label": "A"})

    payload = build_delivery_payload(attempt=attempt)
    assert len(payload) == 1
    entry = payload[0]
    assert entry["exam_question"] == str(exam_question.public_id)
    assert entry["marks"] == "5.00"
    assert entry["response"] == {"selected_option_label": "A"}
    assert entry["flagged"] is False
    # The correct answer must never be shown to the candidate mid-attempt.
    assert all("is_correct" not in option for option in entry["snapshot"]["options"])


@pytest.mark.django_db
def test_save_answer_then_submit_autoscores_and_finalizes(ready_exam):
    candidate = ready_exam["candidate"]
    exam_question = ready_exam["exam"].exam_questions.get()
    attempt = start_attempt(candidate=candidate)

    save_answer(attempt=attempt, exam_question=exam_question, response={"selected_option_label": "B"})
    submitted = submit_attempt(attempt=attempt, actor=None)

    assert submitted.status == "submitted"
    assert submitted.score == Decimal("5.00")
    assert submitted.percentage == Decimal("100.00")
    assert submitted.passed is True
    assert is_fully_graded(attempt=submitted)

    answer = StudentAnswer.objects.get(attempt=attempt)
    assert answer.is_correct is True
    assert answer.marks_awarded == Decimal("5.00")

    result = Result.objects.get(student=ready_exam["student"])
    assert result.score == Decimal("5.00")
    assessment = Assessment.objects.get()
    assert assessment.score_category == "cbt"
    assert assessment.max_score == ready_exam["exam"].total_marks


@pytest.mark.django_db
def test_wrong_answer_scores_zero_and_fails(ready_exam):
    candidate = ready_exam["candidate"]
    exam_question = ready_exam["exam"].exam_questions.get()
    attempt = start_attempt(candidate=candidate)

    save_answer(attempt=attempt, exam_question=exam_question, response={"selected_option_label": "A"})
    submitted = submit_attempt(attempt=attempt, actor=None)

    assert submitted.score == Decimal("0.00")
    assert submitted.passed is False


@pytest.mark.django_db
def test_unanswered_question_scores_zero(ready_exam):
    attempt = start_attempt(candidate=ready_exam["candidate"])

    submitted = submit_attempt(attempt=attempt, actor=None)

    assert submitted.score == Decimal("0.00")
    assert StudentAnswer.objects.filter(attempt=attempt).count() == 0


@pytest.mark.django_db
def test_cannot_answer_after_expiry(ready_exam):
    attempt = start_attempt(candidate=ready_exam["candidate"])
    attempt.expires_at = timezone.now() - timedelta(seconds=1)
    attempt.save(update_fields=["expires_at"])

    exam_question = ready_exam["exam"].exam_questions.get()
    with pytest.raises(AttemptError):
        save_answer(attempt=attempt, exam_question=exam_question, response={"selected_option_label": "B"})


@pytest.mark.django_db
def test_heartbeat_auto_expires_and_finalizes(ready_exam):
    candidate = ready_exam["candidate"]
    exam_question = ready_exam["exam"].exam_questions.get()
    attempt = start_attempt(candidate=candidate)
    save_answer(attempt=attempt, exam_question=exam_question, response={"selected_option_label": "B"})

    attempt.expires_at = timezone.now() - timedelta(seconds=1)
    attempt.save(update_fields=["expires_at"])

    checked = heartbeat(attempt=attempt)

    assert checked.status == "expired"
    assert checked.score == Decimal("5.00")
    assert Result.objects.filter(student=ready_exam["student"]).exists()


@pytest.mark.django_db
def test_heartbeat_is_a_noop_while_time_remains(ready_exam):
    attempt = start_attempt(candidate=ready_exam["candidate"])
    checked = heartbeat(attempt=attempt)
    assert checked.status == "in_progress"


@pytest.mark.django_db
def test_double_submit_is_rejected(ready_exam):
    attempt = start_attempt(candidate=ready_exam["candidate"])
    submit_attempt(attempt=attempt, actor=None)

    with pytest.raises(InvalidAttemptTransition):
        submit_attempt(attempt=attempt, actor=None)


@pytest.mark.django_db
def test_set_flag_does_not_require_an_answer_yet(ready_exam):
    attempt = start_attempt(candidate=ready_exam["candidate"])
    exam_question = ready_exam["exam"].exam_questions.get()

    flagged = set_flag(attempt=attempt, exam_question=exam_question, flagged=True)

    assert flagged.flagged is True
    assert flagged.response == {}


@pytest.mark.django_db
def test_subjective_answer_blocks_finalization_until_manually_graded(
    cbt_exam_fixture_set, cbt_question_factory, student_factory, staff_factory, teacher_factory,
    class_subject_factory, enrollment_factory,
):
    fs = cbt_exam_fixture_set
    exam = fs["exam"]
    exam.start_at = timezone.now() - timedelta(minutes=5)
    exam.end_at = timezone.now() + timedelta(hours=1)
    exam.save(update_fields=["start_at", "end_at"])

    subjective = cbt_question_factory(
        subject=fs["subject"], class_level=fs["class_level"], question_type="short_answer", marks="10.00"
    )
    submit_question(question=subjective, actor=None)
    approve_question(question=subjective, actor=None)
    add_question_to_exam(exam=exam, question=subjective)

    student = student_factory(school=fs["school"])
    enrollment_factory(student=student, class_arm=fs["class_arm"], academic_year=fs["academic_year"])
    teacher = teacher_factory(staff=staff_factory(school=fs["school"]))
    class_subject_factory(class_arm=fs["class_arm"], subject=fs["subject"], teacher=teacher)
    candidate = add_candidate(exam=exam, student=student)
    published = publish_exam(exam=exam, actor=None)

    attempt = start_attempt(candidate=candidate)
    exam_question = published.exam_questions.get()
    save_answer(attempt=attempt, exam_question=exam_question, response={"text": "my essay answer"})

    submitted = submit_attempt(attempt=attempt, actor=None)
    assert submitted.status == "submitted"
    assert not is_fully_graded(attempt=submitted)
    assert not Result.objects.filter(student=student).exists()

    answer = StudentAnswer.objects.get(attempt=attempt)
    with pytest.raises(AttemptError):
        grade_subjective_answer(student_answer=answer, marks_awarded=Decimal("15.00"), actor=None)

    graded = grade_subjective_answer(student_answer=answer, marks_awarded=Decimal("7.00"), actor=None)
    assert graded.graded_at is not None

    attempt.refresh_from_db()
    assert attempt.score == Decimal("7.00")
    result = Result.objects.get(student=student)
    assert result.score == Decimal("7.00")


@pytest.mark.django_db
def test_finalize_fails_clearly_without_a_class_subject_assignment(
    cbt_exam_fixture_set, cbt_question_factory, student_factory, enrollment_factory
):
    fs = cbt_exam_fixture_set
    exam = fs["exam"]
    exam.start_at = timezone.now() - timedelta(minutes=5)
    exam.end_at = timezone.now() + timedelta(hours=1)
    exam.save(update_fields=["start_at", "end_at"])

    question = _single_choice_question(cbt_question_factory, fs)
    add_question_to_exam(exam=exam, question=question)

    student = student_factory(school=fs["school"])
    enrollment_factory(student=student, class_arm=fs["class_arm"], academic_year=fs["academic_year"])
    # Deliberately no class_subject_factory call — no teacher assigned yet.
    candidate = add_candidate(exam=exam, student=student)
    published = publish_exam(exam=exam, actor=None)

    attempt = start_attempt(candidate=candidate)
    exam_question = published.exam_questions.get()
    save_answer(attempt=attempt, exam_question=exam_question, response={"selected_option_label": "B"})

    with pytest.raises(AttemptError):
        submit_attempt(attempt=attempt, actor=None)

    # The attempt itself is still marked submitted/scored even though
    # finalize (the Result write) failed — nothing here should silently
    # discard the student's work.
    attempt.refresh_from_db()
    assert attempt.status == "submitted"
    assert attempt.score == Decimal("5.00")


@pytest.mark.django_db
def test_log_attempt_event_records_but_does_not_flag_below_threshold(ready_exam):
    attempt = start_attempt(candidate=ready_exam["candidate"])

    for _ in range(AUTO_FLAG_THRESHOLD - 1):
        event = log_attempt_event(attempt=attempt, event_type="tab_hidden")
        assert isinstance(event, ExamAttemptEvent)

    attempt.refresh_from_db()
    assert attempt.flagged_for_review is False
    assert attempt.events.count() == AUTO_FLAG_THRESHOLD - 1


@pytest.mark.django_db
def test_log_attempt_event_auto_flags_once_threshold_is_reached(ready_exam):
    attempt = start_attempt(candidate=ready_exam["candidate"])

    for _ in range(AUTO_FLAG_THRESHOLD):
        log_attempt_event(attempt=attempt, event_type="fullscreen_exit")

    attempt.refresh_from_db()
    assert attempt.flagged_for_review is True


@pytest.mark.django_db
def test_benign_event_types_never_count_toward_flagging(ready_exam):
    attempt = start_attempt(candidate=ready_exam["candidate"])

    for _ in range(AUTO_FLAG_THRESHOLD * 5):
        log_attempt_event(attempt=attempt, event_type="tab_visible")

    attempt.refresh_from_db()
    assert attempt.flagged_for_review is False


@pytest.mark.django_db
def test_log_attempt_event_requires_an_open_attempt(ready_exam):
    attempt = start_attempt(candidate=ready_exam["candidate"])
    exam_question = ready_exam["exam"].exam_questions.get()
    save_answer(attempt=attempt, exam_question=exam_question, response={"selected_option_label": "B"})
    submit_attempt(attempt=attempt, actor=None)

    with pytest.raises(AttemptError):
        log_attempt_event(attempt=attempt, event_type="tab_hidden")
