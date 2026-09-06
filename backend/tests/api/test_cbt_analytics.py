"""apps.cbt Phase 7: post-hoc exam analytics (analytics_service +
ExamAnalyticsView). Builds a small, fully-graded population of finalized
attempts to exercise exam_summary and item_analysis with known, hand-
computed expected values.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.cbt.models import QuestionOption
from apps.cbt.services.analytics_service import exam_summary, item_analysis
from apps.cbt.services.attempt_service import save_answer, start_attempt, submit_attempt
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


def _choice_question(cbt_question_factory, fs, correct_label="B", marks="5.00"):
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
def graded_exam(
    cbt_exam_fixture_set, cbt_question_factory, student_factory, staff_factory, teacher_factory,
    class_subject_factory, enrollment_factory,
):
    """A published exam with two 5-mark single_choice questions (B
    correct), pass_mark 5, and four candidates whose attempts are already
    submitted and fully auto-graded: two score 10/10 (100%), two score
    0/10 (0%) — a clean, hand-computable population for analytics.
    """
    fs = cbt_exam_fixture_set
    exam = fs["exam"]
    exam.start_at = timezone.now() - timedelta(minutes=5)
    exam.end_at = timezone.now() + timedelta(hours=1)
    exam.duration_minutes = 30
    exam.pass_mark = Decimal("5.00")
    exam.save(update_fields=["start_at", "end_at", "duration_minutes", "pass_mark"])

    q1 = _choice_question(cbt_question_factory, fs)
    q2 = _choice_question(cbt_question_factory, fs)
    add_question_to_exam(exam=exam, question=q1)
    add_question_to_exam(exam=exam, question=q2)

    teacher = teacher_factory(staff=staff_factory(school=fs["school"]))
    class_subject_factory(class_arm=fs["class_arm"], subject=fs["subject"], teacher=teacher)

    students = []
    candidates = []
    for admission_number in ["A001", "A002", "A003", "A004"]:
        student = student_factory(school=fs["school"], admission_number=admission_number)
        enrollment_factory(student=student, class_arm=fs["class_arm"], academic_year=fs["academic_year"])
        candidates.append(add_candidate(exam=exam, student=student))
        students.append(student)

    published = publish_exam(exam=exam, actor=None)
    eq1, eq2 = published.exam_questions.order_by("order")

    for i, candidate in enumerate(candidates):
        attempt = start_attempt(candidate=candidate)
        # First two students (i < 2) answer correctly (B); the other two
        # answer incorrectly (A) — a clean 50/50 split for facility and
        # discrimination.
        chosen = "B" if i < 2 else "A"
        save_answer(attempt=attempt, exam_question=eq1, response={"selected_option_label": chosen})
        save_answer(attempt=attempt, exam_question=eq2, response={"selected_option_label": chosen})
        submit_attempt(attempt=attempt, actor=None)
        students.append(student)

    return {**fs, "exam": published, "eq1": eq1, "eq2": eq2, "students": students}


@pytest.mark.django_db
def test_exam_summary_with_no_attempts_at_all(cbt_exam_fixture_set):
    summary = exam_summary(exam=cbt_exam_fixture_set["exam"])
    assert summary["finalized_attempts"] == 0
    assert summary["average_score"] is None
    assert summary["pass_rate"] is None
    assert summary["score_distribution"][0] == {"range": "0-9", "count": 0}


@pytest.mark.django_db
def test_exam_summary_computes_averages_pass_rate_and_distribution(graded_exam):
    summary = exam_summary(exam=graded_exam["exam"])

    assert summary["total_candidates"] == 4
    assert summary["finalized_attempts"] == 4
    assert summary["average_score"] == "5.00"
    assert summary["average_percentage"] == "50.00"
    assert summary["pass_rate"] == "50.00"

    distribution = {row["range"]: row["count"] for row in summary["score_distribution"]}
    assert distribution["0-9"] == 2
    assert distribution["90-100"] == 2


@pytest.mark.django_db
def test_item_analysis_facility_and_discrimination(graded_exam):
    items = item_analysis(exam=graded_exam["exam"])
    assert len(items) == 2

    for row in items:
        assert row["answered_count"] == 4
        assert row["correct_count"] == 2
        assert row["facility_index"] == "0.50"
        # group_size = round(4 * 0.27) -> 1: the single top scorer got
        # this question right, the single bottom scorer got it wrong.
        assert row["discrimination_index"] == "1.00"


@pytest.mark.django_db
def test_analytics_excludes_attempts_still_pending_manual_grading(
    cbt_exam_fixture_set, cbt_question_factory, student_factory, staff_factory, teacher_factory,
    class_subject_factory, enrollment_factory,
):
    fs = cbt_exam_fixture_set
    exam = fs["exam"]
    exam.start_at = timezone.now() - timedelta(minutes=5)
    exam.end_at = timezone.now() + timedelta(hours=1)
    exam.save(update_fields=["start_at", "end_at"])

    subjective = cbt_question_factory(
        subject=fs["subject"], class_level=fs["class_level"], question_type="short_answer", marks="5.00"
    )
    submit_question(question=subjective, actor=None)
    approve_question(question=subjective, actor=None)
    add_question_to_exam(exam=exam, question=subjective)

    teacher = teacher_factory(staff=staff_factory(school=fs["school"]))
    class_subject_factory(class_arm=fs["class_arm"], subject=fs["subject"], teacher=teacher)

    student = student_factory(school=fs["school"])
    enrollment_factory(student=student, class_arm=fs["class_arm"], academic_year=fs["academic_year"])
    candidate = add_candidate(exam=exam, student=student)
    published = publish_exam(exam=exam, actor=None)

    attempt = start_attempt(candidate=candidate)
    eq = published.exam_questions.get()
    save_answer(attempt=attempt, exam_question=eq, response={"text": "an ungraded essay"})
    submit_attempt(attempt=attempt, actor=None)
    assert attempt.status == "submitted"  # submitted, but not yet fully graded

    summary = exam_summary(exam=published)
    assert summary["finalized_attempts"] == 0  # excluded: still awaiting a human grade


@pytest.mark.django_db
def test_analytics_endpoint_requires_permission_and_returns_summary_and_items(
    api_client, organization, user_factory, graded_exam
):
    exam = graded_exam["exam"]

    norole = user_factory(organization=organization, email="norole@example.com", password="s3cret-pass!")
    _login(api_client, "norole@example.com", "s3cret-pass!")
    denied = api_client.get(f"/api/v1/cbt/exams/{exam.public_id}/analytics")
    assert denied.status_code == 403

    staff = user_factory(organization=organization, email="staff@example.com", password="s3cret-pass!")
    _grant(staff, "cbt_exams.view")
    _login(api_client, "staff@example.com", "s3cret-pass!")

    resp = api_client.get(f"/api/v1/cbt/exams/{exam.public_id}/analytics")
    assert resp.status_code == 200, resp.json()
    data = resp.json()["data"]
    assert data["summary"]["finalized_attempts"] == 4
    assert len(data["items"]) == 2
