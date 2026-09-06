"""apps.cbt Phase 4: the DRF API surface on top of attempt_service
(backend/tests/api/test_cbt_attempts.py already covers that layer
directly). Self-service endpoints (start/heartbeat/answers/flag/submit)
are ownership-gated, never RBAC-gated — every student must always be able
to act on their own attempt. Staff endpoints (list/detail/grade) are
RBAC-gated and org-wide, with no ownership narrowing.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.cbt.models import QuestionOption
from apps.cbt.services.exam_service import add_candidate, add_question_to_exam, publish_exam
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
def ready_exam(
    cbt_exam_fixture_set, cbt_question_factory, student_factory, staff_factory, teacher_factory,
    class_subject_factory, enrollment_factory, organization, user_factory,
):
    """A published exam, one single_choice question (B is correct, 5
    marks), one eligible candidate — a student user attached to that
    candidate so the self-service API can log in as them — plus a second,
    unrelated student to prove ownership scoping.
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

    student_user = user_factory(organization=organization, email="candidate@example.com", password="s3cret-pass!")
    student = student_factory(school=fs["school"], user=student_user)
    enrollment_factory(student=student, class_arm=fs["class_arm"], academic_year=fs["academic_year"])
    teacher = teacher_factory(staff=staff_factory(school=fs["school"]))
    class_subject_factory(class_arm=fs["class_arm"], subject=fs["subject"], teacher=teacher)
    candidate = add_candidate(exam=exam, student=student)

    other_user = user_factory(organization=organization, email="other@example.com", password="s3cret-pass!")
    other_student = student_factory(
        school=fs["school"], admission_number="A002", first_name="Other", user=other_user
    )

    published = publish_exam(exam=exam, actor=None)
    return {
        **fs,
        "exam": published,
        "question": question,
        "student": student,
        "candidate": candidate,
        "other_student": other_student,
    }


@pytest.mark.django_db
def test_student_can_start_answer_and_submit_own_attempt_via_api(api_client, ready_exam):
    candidate = ready_exam["candidate"]
    exam_question = ready_exam["exam"].exam_questions.get()
    _login(api_client, "candidate@example.com", "s3cret-pass!")

    started = api_client.post(f"/api/v1/cbt/my/candidates/{candidate.public_id}/start-attempt")
    assert started.status_code == 200, started.json()
    body = started.json()["data"]
    assert body["attempt"]["status"] == "in_progress"
    assert len(body["questions"]) == 1
    delivered = body["questions"][0]
    assert delivered["exam_question"] == str(exam_question.public_id)
    # The candidate must never see which option is correct mid-attempt.
    for option in delivered["snapshot"]["options"]:
        assert "is_correct" not in option
    attempt_public_id = body["attempt"]["public_id"]

    heartbeat = api_client.post(f"/api/v1/cbt/my/attempts/{attempt_public_id}/heartbeat")
    assert heartbeat.status_code == 200
    assert heartbeat.json()["data"]["attempt"]["status"] == "in_progress"

    answered = api_client.post(
        f"/api/v1/cbt/my/attempts/{attempt_public_id}/answers",
        {"exam_question": str(exam_question.public_id), "response": {"selected_option_label": "B"}},
        format="json",
    )
    assert answered.status_code == 200, answered.json()
    assert answered.json()["data"]["response"] == {"selected_option_label": "B"}

    flagged = api_client.post(
        f"/api/v1/cbt/my/attempts/{attempt_public_id}/flag",
        {"exam_question": str(exam_question.public_id), "flagged": True},
        format="json",
    )
    assert flagged.status_code == 200
    assert flagged.json()["data"]["flagged"] is True

    submitted = api_client.post(f"/api/v1/cbt/my/attempts/{attempt_public_id}/submit")
    assert submitted.status_code == 200, submitted.json()
    submitted_attempt = submitted.json()["data"]["attempt"]
    assert submitted_attempt["status"] == "submitted"
    assert submitted_attempt["score"] == "5.00"
    assert submitted_attempt["passed"] is True

    detail = api_client.get(f"/api/v1/cbt/my/attempts/{attempt_public_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["attempt"]["status"] == "submitted"


@pytest.mark.django_db
def test_student_cannot_start_or_view_another_students_attempt(api_client, ready_exam):
    candidate = ready_exam["candidate"]
    _login(api_client, "other@example.com", "s3cret-pass!")

    denied_start = api_client.post(f"/api/v1/cbt/my/candidates/{candidate.public_id}/start-attempt")
    assert denied_start.status_code == 404

    from apps.cbt.services.attempt_service import start_attempt

    attempt = start_attempt(candidate=candidate)
    denied_detail = api_client.get(f"/api/v1/cbt/my/attempts/{attempt.public_id}")
    assert denied_detail.status_code == 404

    denied_submit = api_client.post(f"/api/v1/cbt/my/attempts/{attempt.public_id}/submit")
    assert denied_submit.status_code == 404


@pytest.mark.django_db
def test_self_service_endpoints_require_a_student_profile(api_client, organization, user_factory, ready_exam):
    candidate = ready_exam["candidate"]
    staff_user = user_factory(organization=organization, email="staffonly@example.com", password="s3cret-pass!")
    _login(api_client, "staffonly@example.com", "s3cret-pass!")

    resp = api_client.post(f"/api/v1/cbt/my/candidates/{candidate.public_id}/start-attempt")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_staff_list_and_detail_require_permission_and_see_every_attempt(api_client, organization, user_factory, ready_exam):
    from apps.cbt.services.attempt_service import save_answer, start_attempt, submit_attempt

    exam = ready_exam["exam"]
    candidate = ready_exam["candidate"]
    exam_question = exam.exam_questions.get()
    attempt = start_attempt(candidate=candidate)
    save_answer(attempt=attempt, exam_question=exam_question, response={"selected_option_label": "B"})
    submit_attempt(attempt=attempt, actor=None)

    norole = user_factory(organization=organization, email="norole@example.com", password="s3cret-pass!")
    _login(api_client, "norole@example.com", "s3cret-pass!")
    denied = api_client.get(f"/api/v1/cbt/exams/{exam.public_id}/attempts")
    assert denied.status_code == 403

    staff = user_factory(organization=organization, email="staff2@example.com", password="s3cret-pass!")
    _grant(staff, "cbt_attempts.view")
    _login(api_client, "staff2@example.com", "s3cret-pass!")

    listed = api_client.get(f"/api/v1/cbt/exams/{exam.public_id}/attempts")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1

    detail = api_client.get(f"/api/v1/cbt/exams/{exam.public_id}/attempts/{attempt.public_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["attempt"]["status"] == "submitted"
    assert len(detail.json()["data"]["answers"]) == 1


@pytest.mark.django_db
def test_staff_grade_requires_permission_and_finalizes_result(
    api_client, organization, user_factory, cbt_exam_fixture_set, cbt_question_factory,
    student_factory, staff_factory, teacher_factory, class_subject_factory, enrollment_factory,
):
    from apps.cbt.services.attempt_service import save_answer, start_attempt, submit_attempt
    from apps.examinations.models import Result

    fs = cbt_exam_fixture_set
    exam = fs["exam"]
    exam.start_at = timezone.now() - timedelta(minutes=5)
    exam.end_at = timezone.now() + timedelta(hours=1)
    exam.save(update_fields=["start_at", "end_at"])

    mc = _single_choice_question(cbt_question_factory, fs)
    add_question_to_exam(exam=exam, question=mc)
    subjective = cbt_question_factory(
        subject=fs["subject"], class_level=fs["class_level"], question_type="short_answer", marks="5.00"
    )
    submit_question(question=subjective, actor=None)
    approve_question(question=subjective, actor=None)
    subjective_eq = add_question_to_exam(exam=exam, question=subjective)

    student = student_factory(school=fs["school"])
    enrollment_factory(student=student, class_arm=fs["class_arm"], academic_year=fs["academic_year"])
    teacher = teacher_factory(staff=staff_factory(school=fs["school"]))
    class_subject_factory(class_arm=fs["class_arm"], subject=fs["subject"], teacher=teacher)
    candidate = add_candidate(exam=exam, student=student)
    exam = publish_exam(exam=exam, actor=None)

    attempt = start_attempt(candidate=candidate)
    mc_eq = exam.exam_questions.get(question=mc)
    save_answer(attempt=attempt, exam_question=mc_eq, response={"selected_option_label": "B"})
    save_answer(attempt=attempt, exam_question=subjective_eq, response={"text": "an essay answer"})
    submit_attempt(attempt=attempt, actor=None)
    assert attempt.status == "submitted"
    assert not Result.objects.filter(student=student).exists()

    subjective_answer = attempt.answers.get(exam_question=subjective_eq)

    norole = user_factory(organization=organization, email="norole2@example.com", password="s3cret-pass!")
    _login(api_client, "norole2@example.com", "s3cret-pass!")
    denied = api_client.post(
        f"/api/v1/cbt/answers/{subjective_answer.public_id}/grade", {"marks_awarded": "5.00"}, format="json"
    )
    assert denied.status_code == 403

    grader = user_factory(organization=organization, email="grader@example.com", password="s3cret-pass!")
    _grant(grader, "cbt_attempts.grade")
    _login(api_client, "grader@example.com", "s3cret-pass!")

    graded = api_client.post(
        f"/api/v1/cbt/answers/{subjective_answer.public_id}/grade", {"marks_awarded": "5.00"}, format="json"
    )
    assert graded.status_code == 200, graded.json()
    assert graded.json()["data"]["marks_awarded"] == "5.00"

    result = Result.objects.get(student=student)
    assert result.score == Decimal("10.00")
