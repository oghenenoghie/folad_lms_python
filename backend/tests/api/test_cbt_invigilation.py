"""apps.cbt Phase 9: live invigilation — a staff-facing, poll-based
snapshot of every candidate's status during an exam window
(invigilation_service.live_status + ExamLiveStatusView).
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.cbt.models import QuestionOption
from apps.cbt.services.attempt_service import log_attempt_event, save_answer, start_attempt
from apps.cbt.services.exam_service import add_candidate, add_question_to_exam, publish_exam
from apps.cbt.services.invigilation_service import live_status
from apps.cbt.services.question_service import approve_question, submit_question


def _grant(user, *codes):
    role = Role.objects.create(name=f"ROLE_{user.pk}_{'_'.join(codes)}"[:100], label="Test Role")
    for code in codes:
        RolePermission.objects.create(role=role, permission=Permission.objects.get(code=code))
    UserRole.objects.create(user=user, role=role)


def _login(api_client, email, password):
    resp = api_client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    token = resp.json()["data"]["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


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
def live_exam(
    cbt_exam_fixture_set, cbt_question_factory, student_factory, staff_factory, teacher_factory,
    class_subject_factory, enrollment_factory,
):
    """A published exam with one question, two candidates: one who never
    starts, one who starts, answers, and logs a proctoring event.
    """
    fs = cbt_exam_fixture_set
    exam = fs["exam"]
    exam.start_at = timezone.now() - timedelta(minutes=5)
    exam.end_at = timezone.now() + timedelta(hours=1)
    exam.duration_minutes = 30
    exam.pass_mark = Decimal("3.00")
    exam.save(update_fields=["start_at", "end_at", "duration_minutes", "pass_mark"])

    question = _single_choice_question(cbt_question_factory, fs)
    add_question_to_exam(exam=exam, question=question)

    teacher = teacher_factory(staff=staff_factory(school=fs["school"]))
    class_subject_factory(class_arm=fs["class_arm"], subject=fs["subject"], teacher=teacher)

    not_started_student = student_factory(school=fs["school"], admission_number="A001")
    enrollment_factory(student=not_started_student, class_arm=fs["class_arm"], academic_year=fs["academic_year"])
    not_started_candidate = add_candidate(exam=exam, student=not_started_student)

    active_student = student_factory(school=fs["school"], admission_number="A002")
    enrollment_factory(student=active_student, class_arm=fs["class_arm"], academic_year=fs["academic_year"])
    active_candidate = add_candidate(exam=exam, student=active_student)

    published = publish_exam(exam=exam, actor=None)
    return {
        **fs, "exam": published, "question": question,
        "not_started_candidate": not_started_candidate, "active_candidate": active_candidate,
    }


@pytest.mark.django_db
def test_live_status_reports_not_started_candidate(live_exam):
    rows = live_status(exam=live_exam["exam"])
    row = next(r for r in rows if r["candidate"] == str(live_exam["not_started_candidate"].public_id))
    assert row["status"] == "not_started"
    assert row["answered_count"] == 0
    assert row["total_questions"] == 1
    assert row["seconds_remaining"] is None
    assert row["flagged_for_review"] is False
    assert row["last_activity_at"] is None


@pytest.mark.django_db
def test_live_status_reports_in_progress_candidate_with_progress_and_countdown(live_exam):
    exam_question = live_exam["exam"].exam_questions.get()
    attempt = start_attempt(candidate=live_exam["active_candidate"])
    save_answer(attempt=attempt, exam_question=exam_question, response={"selected_option_label": "B"})

    rows = live_status(exam=live_exam["exam"])
    row = next(r for r in rows if r["candidate"] == str(live_exam["active_candidate"].public_id))
    assert row["status"] == "in_progress"
    assert row["answered_count"] == 1
    assert row["total_questions"] == 1
    assert row["seconds_remaining"] is not None
    assert 0 < row["seconds_remaining"] <= 30 * 60
    assert row["last_activity_at"] is not None


@pytest.mark.django_db
def test_live_status_reflects_flagged_for_review(live_exam):
    from apps.cbt.services.attempt_service import AUTO_FLAG_THRESHOLD

    attempt = start_attempt(candidate=live_exam["active_candidate"])
    for _ in range(AUTO_FLAG_THRESHOLD):
        log_attempt_event(attempt=attempt, event_type="tab_hidden")

    rows = live_status(exam=live_exam["exam"])
    row = next(r for r in rows if r["candidate"] == str(live_exam["active_candidate"].public_id))
    assert row["flagged_for_review"] is True
    assert row["last_activity_at"] is not None


@pytest.mark.django_db
def test_live_status_endpoint_requires_permission(api_client, organization, user_factory, live_exam):
    exam = live_exam["exam"]

    norole = user_factory(organization=organization, email="norole@example.com", password="s3cret-pass!")
    _login(api_client, "norole@example.com", "s3cret-pass!")
    denied = api_client.get(f"/api/v1/cbt/exams/{exam.public_id}/live")
    assert denied.status_code == 403

    staff = user_factory(organization=organization, email="staff@example.com", password="s3cret-pass!")
    _grant(staff, "cbt_attempts.view")
    _login(api_client, "staff@example.com", "s3cret-pass!")

    resp = api_client.get(f"/api/v1/cbt/exams/{exam.public_id}/live")
    assert resp.status_code == 200, resp.json()
    data = resp.json()["data"]
    assert "server_time" in data
    assert len(data["candidates"]) == 2
