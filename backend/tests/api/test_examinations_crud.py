import pytest
from django.db import ProgrammingError, connection, transaction

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.examinations.models import Result, ResultWorkflowState
from apps.tenancy.context import activate_organization


def _grant(user, *codes):
    role = Role.objects.create(name=f"ROLE_{user.pk}_{'_'.join(codes)}"[:100], label="Test Role")
    for code in codes:
        RolePermission.objects.create(role=role, permission=Permission.objects.get(code=code))
    UserRole.objects.create(user=user, role=role)


def _login(api_client, email, password):
    resp = api_client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    token = resp.json()["data"]["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def _class_subject(
    organization, school_factory, campus_factory, class_level_factory, class_arm_factory,
    subject_factory, staff_factory, teacher_factory, class_subject_factory,
):
    school = school_factory(organization=organization)
    class_arm = class_arm_factory(class_level=class_level_factory(campus=campus_factory(school=school)))
    subject = subject_factory(school=school)
    teacher = teacher_factory(staff=staff_factory(school=school))
    return class_subject_factory(class_arm=class_arm, subject=subject, teacher=teacher)


@pytest.fixture
def exam_fixture_set(
    organization, school_factory, campus_factory, class_level_factory, class_arm_factory,
    subject_factory, staff_factory, teacher_factory, class_subject_factory,
    academic_year_factory, term_factory, student_factory,
):
    class_subject = _class_subject(
        organization, school_factory, campus_factory, class_level_factory, class_arm_factory,
        subject_factory, staff_factory, teacher_factory, class_subject_factory,
    )
    school = class_subject.class_arm.class_level.campus.school
    academic_year = academic_year_factory(school=school)
    term = term_factory(academic_year=academic_year)
    student = student_factory(school=school)
    return {
        "school": school,
        "class_subject": class_subject,
        "teacher": class_subject.teacher,
        "term": term,
        "student": student,
    }


@pytest.mark.django_db
def test_assessment_and_result_crud(api_client, organization, user_factory, exam_fixture_set):
    class_subject = exam_fixture_set["class_subject"]
    term = exam_fixture_set["term"]
    student = exam_fixture_set["student"]

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(
        user,
        "assessments.view", "assessments.create",
        "results.view", "results.create", "results.update", "results.delete",
    )
    _login(api_client, "a@example.com", "s3cret-pass!")

    created_assessment = api_client.post(
        "/api/v1/assessments",
        {
            "class_subject": str(class_subject.public_id),
            "term": str(term.public_id),
            "name": "Mid-term Test",
            "assessment_type": "test",
            "weight": "30.00",
            "max_score": "100.00",
        },
        format="json",
    )
    assert created_assessment.status_code == 201
    assessment_public_id = created_assessment.json()["data"]["public_id"]

    created_result = api_client.post(
        "/api/v1/results",
        {
            "assessment": assessment_public_id,
            "student": str(student.public_id),
            "score": "85.00",
        },
        format="json",
    )
    assert created_result.status_code == 201
    result_body = created_result.json()["data"]
    assert result_body["status"] == "entered"
    result_public_id = result_body["public_id"]

    updated = api_client.patch(f"/api/v1/results/{result_public_id}", {"score": "90.00"}, format="json")
    assert updated.status_code == 200
    assert updated.json()["data"]["score"] == "90.00"

    deleted = api_client.delete(f"/api/v1/results/{result_public_id}")
    assert deleted.status_code == 200
    assert api_client.get(f"/api/v1/results/{result_public_id}").status_code == 404


@pytest.mark.django_db
def test_result_grade_resolved_from_default_grading_scheme(
    api_client, organization, user_factory, exam_fixture_set,
    grading_scheme_factory, grade_band_factory, assessment_factory,
):
    school = exam_fixture_set["school"]
    class_subject = exam_fixture_set["class_subject"]
    term = exam_fixture_set["term"]
    student = exam_fixture_set["student"]

    grading_scheme = grading_scheme_factory(school=school)
    grade_band_factory(grading_scheme=grading_scheme, grade="A", min_score="70.00", max_score="100.00")
    grade_band_factory(grading_scheme=grading_scheme, grade="B", min_score="50.00", max_score="69.99")
    assessment = assessment_factory(class_subject=class_subject, term=term)

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "results.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    created = api_client.post(
        "/api/v1/results",
        {"assessment": str(assessment.public_id), "student": str(student.public_id), "score": "75.00"},
        format="json",
    )
    assert created.status_code == 201
    assert created.json()["data"]["grade"] == "A"


@pytest.mark.django_db
def test_result_workflow_happy_path_and_audit_trail(
    api_client, organization, user_factory, exam_fixture_set, assessment_factory, result_factory,
):
    class_subject = exam_fixture_set["class_subject"]
    term = exam_fixture_set["term"]
    student = exam_fixture_set["student"]
    assessment = assessment_factory(class_subject=class_subject, term=term)
    result = result_factory(assessment=assessment, student=student)

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "results.submit", "results.review", "results.verify", "results.publish", "results.view")
    _login(api_client, "a@example.com", "s3cret-pass!")

    for step, expected_status in [
        ("submit", "submitted"),
        ("review", "reviewed"),
        ("verify", "verified"),
        ("publish", "published"),
    ]:
        resp = api_client.post(f"/api/v1/results/{result.public_id}/{step}")
        assert resp.status_code == 200, resp.json()
        assert resp.json()["data"]["status"] == expected_status

    result.refresh_from_db()
    assert result.status == "published"

    history = api_client.get(f"/api/v1/result-workflow-states?result_id={result.public_id}")
    entries = history.json()["data"]["results"]
    assert len(entries) == 4
    assert {e["new_status"] for e in entries} == {"submitted", "reviewed", "verified", "published"}


@pytest.mark.django_db
def test_result_workflow_rejects_out_of_order_transition(
    api_client, organization, user_factory, exam_fixture_set, assessment_factory, result_factory,
):
    class_subject = exam_fixture_set["class_subject"]
    term = exam_fixture_set["term"]
    student = exam_fixture_set["student"]
    assessment = assessment_factory(class_subject=class_subject, term=term)
    result = result_factory(assessment=assessment, student=student)

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "results.review", "results.publish")
    _login(api_client, "a@example.com", "s3cret-pass!")

    skip_ahead = api_client.post(f"/api/v1/results/{result.public_id}/review")
    assert skip_ahead.status_code == 409
    assert skip_ahead.json()["success"] is False

    publish_before_submit = api_client.post(f"/api/v1/results/{result.public_id}/publish")
    assert publish_before_submit.status_code == 409


@pytest.mark.django_db
def test_result_cannot_be_edited_once_submitted(
    api_client, organization, user_factory, exam_fixture_set, assessment_factory, result_factory,
):
    class_subject = exam_fixture_set["class_subject"]
    term = exam_fixture_set["term"]
    student = exam_fixture_set["student"]
    assessment = assessment_factory(class_subject=class_subject, term=term)
    result = result_factory(assessment=assessment, student=student)

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "results.submit", "results.update")
    _login(api_client, "a@example.com", "s3cret-pass!")

    api_client.post(f"/api/v1/results/{result.public_id}/submit")

    blocked = api_client.patch(f"/api/v1/results/{result.public_id}", {"score": "10.00"}, format="json")
    assert blocked.status_code == 409


@pytest.mark.django_db
def test_examinations_app_layer_tenant_isolation(
    organization, other_organization, school_factory, campus_factory, class_level_factory,
    class_arm_factory, subject_factory, staff_factory, teacher_factory, class_subject_factory,
    academic_year_factory, term_factory, student_factory, assessment_factory, result_factory,
):
    cs_a = _class_subject(
        organization, school_factory, campus_factory, class_level_factory, class_arm_factory,
        subject_factory, staff_factory, teacher_factory, class_subject_factory,
    )
    cs_b = _class_subject(
        other_organization, school_factory, campus_factory, class_level_factory, class_arm_factory,
        subject_factory, staff_factory, teacher_factory, class_subject_factory,
    )
    term_a = term_factory(academic_year=academic_year_factory(school=cs_a.class_arm.class_level.campus.school))
    term_b = term_factory(academic_year=academic_year_factory(school=cs_b.class_arm.class_level.campus.school))
    student_a = student_factory(school=cs_a.class_arm.class_level.campus.school)
    student_b = student_factory(school=cs_b.class_arm.class_level.campus.school)
    assessment_a = assessment_factory(class_subject=cs_a, term=term_a)
    assessment_b = assessment_factory(class_subject=cs_b, term=term_b)
    result_factory(assessment=assessment_a, student=student_a)
    result_factory(assessment=assessment_b, student=student_b)

    activate_organization(organization.id)
    visible = Result.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id


@pytest.mark.skipif(connection.vendor != "postgresql", reason="append-only trigger is Postgres-only")
@pytest.mark.django_db
def test_result_workflow_state_is_append_only_at_db_level(
    organization, exam_fixture_set, assessment_factory, result_factory,
):
    class_subject = exam_fixture_set["class_subject"]
    term = exam_fixture_set["term"]
    student = exam_fixture_set["student"]
    assessment = assessment_factory(class_subject=class_subject, term=term)
    result = result_factory(assessment=assessment, student=student)

    activate_organization(organization.id)
    state = ResultWorkflowState.all_tenants.create(
        organization=organization, result=result, previous_status="entered", new_status="submitted"
    )

    with pytest.raises(ProgrammingError, match="append-only"):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE examinations_result_workflow_state SET new_status = %s WHERE id = %s",
                    ["reviewed", state.id],
                )

    with pytest.raises(ProgrammingError, match="append-only"):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM examinations_result_workflow_state WHERE id = %s", [state.id]
                )


@pytest.mark.django_db
def test_question_and_question_option_crud(
    api_client, organization, user_factory, exam_fixture_set, assessment_factory,
):
    class_subject = exam_fixture_set["class_subject"]
    term = exam_fixture_set["term"]
    assessment = assessment_factory(class_subject=class_subject, term=term)

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(
        user,
        "questions.view", "questions.create", "questions.update", "questions.delete",
        "question_options.view", "question_options.create",
    )
    _login(api_client, "a@example.com", "s3cret-pass!")

    created_question = api_client.post(
        "/api/v1/questions",
        {
            "assessment": str(assessment.public_id),
            "question_type": "multiple_choice",
            "text": "What is the capital of Nigeria?",
            "marks": "10.00",
            "sequence": 1,
        },
        format="json",
    )
    assert created_question.status_code == 201
    question_public_id = created_question.json()["data"]["public_id"]

    created_option = api_client.post(
        "/api/v1/question-options",
        {"question": question_public_id, "text": "Abuja", "is_correct": True, "sequence": 1},
        format="json",
    )
    assert created_option.status_code == 201

    updated = api_client.patch(
        f"/api/v1/questions/{question_public_id}", {"marks": "15.00"}, format="json"
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["marks"] == "15.00"

    deleted = api_client.delete(f"/api/v1/questions/{question_public_id}")
    assert deleted.status_code == 200


@pytest.mark.django_db
def test_objective_answer_auto_grades_on_submit(
    api_client, organization, user_factory, exam_fixture_set, assessment_factory,
    question_factory, question_option_factory,
):
    class_subject = exam_fixture_set["class_subject"]
    term = exam_fixture_set["term"]
    student = exam_fixture_set["student"]
    assessment = assessment_factory(class_subject=class_subject, term=term)
    question = question_factory(assessment=assessment, question_type="multiple_choice", marks="10.00")
    correct_option = question_option_factory(question=question, text="Right", is_correct=True, sequence=1)
    question_option_factory(question=question, text="Wrong", is_correct=False, sequence=2)

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "student_answers.view", "student_answers.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    resp = api_client.post(
        "/api/v1/student-answers",
        {
            "question": str(question.public_id),
            "student": str(student.public_id),
            "selected_option": str(correct_option.public_id),
        },
        format="json",
    )
    assert resp.status_code == 201, resp.json()
    body = resp.json()["data"]
    assert body["is_correct"] is True
    assert body["marks_awarded"] == "10.00"


@pytest.mark.django_db
def test_true_false_answer_auto_grades_incorrect(
    api_client, organization, user_factory, exam_fixture_set, assessment_factory,
    question_factory, question_option_factory,
):
    class_subject = exam_fixture_set["class_subject"]
    term = exam_fixture_set["term"]
    student = exam_fixture_set["student"]
    assessment = assessment_factory(class_subject=class_subject, term=term)
    question = question_factory(assessment=assessment, question_type="true_false", marks="5.00")
    true_option = question_option_factory(question=question, text="True", is_correct=True, sequence=1)
    false_option = question_option_factory(question=question, text="False", is_correct=False, sequence=2)

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "student_answers.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    resp = api_client.post(
        "/api/v1/student-answers",
        {
            "question": str(question.public_id),
            "student": str(student.public_id),
            "selected_option": str(false_option.public_id),
        },
        format="json",
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["is_correct"] is False
    assert body["marks_awarded"] == "0.00"
    assert true_option.is_correct is True


@pytest.mark.django_db
def test_objective_answer_requires_selected_option(
    api_client, organization, user_factory, exam_fixture_set, assessment_factory, question_factory,
):
    class_subject = exam_fixture_set["class_subject"]
    term = exam_fixture_set["term"]
    student = exam_fixture_set["student"]
    assessment = assessment_factory(class_subject=class_subject, term=term)
    question = question_factory(assessment=assessment, question_type="multiple_choice")

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "student_answers.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    resp = api_client.post(
        "/api/v1/student-answers",
        {"question": str(question.public_id), "student": str(student.public_id)},
        format="json",
    )
    assert resp.status_code == 422
    assert resp.json()["success"] is False


@pytest.mark.django_db
def test_subjective_answer_requires_text_and_needs_manual_grading(
    api_client, organization, user_factory, exam_fixture_set, assessment_factory, question_factory,
):
    class_subject = exam_fixture_set["class_subject"]
    term = exam_fixture_set["term"]
    student = exam_fixture_set["student"]
    assessment = assessment_factory(class_subject=class_subject, term=term)
    question = question_factory(assessment=assessment, question_type="essay", marks="20.00", sequence=1)

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "student_answers.create", "student_answers.grade")
    _login(api_client, "a@example.com", "s3cret-pass!")

    blank = api_client.post(
        "/api/v1/student-answers",
        {"question": str(question.public_id), "student": str(student.public_id), "text_answer": "   "},
        format="json",
    )
    assert blank.status_code == 422

    submitted = api_client.post(
        "/api/v1/student-answers",
        {
            "question": str(question.public_id),
            "student": str(student.public_id),
            "text_answer": "Lagos was Nigeria's first capital.",
        },
        format="json",
    )
    assert submitted.status_code == 201
    body = submitted.json()["data"]
    assert body["is_correct"] is None
    assert body["marks_awarded"] is None
    answer_public_id = body["public_id"]

    graded = api_client.post(
        f"/api/v1/student-answers/{answer_public_id}/grade",
        {"marks_awarded": "15.00", "is_correct": True},
        format="json",
    )
    assert graded.status_code == 200, graded.json()
    graded_body = graded.json()["data"]
    assert graded_body["marks_awarded"] == "15.00"
    assert graded_body["is_correct"] is True


@pytest.mark.django_db
def test_duplicate_answer_for_same_question_and_student_conflicts(
    api_client, organization, user_factory, exam_fixture_set, assessment_factory,
    question_factory, question_option_factory,
):
    class_subject = exam_fixture_set["class_subject"]
    term = exam_fixture_set["term"]
    student = exam_fixture_set["student"]
    assessment = assessment_factory(class_subject=class_subject, term=term)
    question = question_factory(assessment=assessment, question_type="multiple_choice")
    option = question_option_factory(question=question, is_correct=True)

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "student_answers.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    payload = {
        "question": str(question.public_id),
        "student": str(student.public_id),
        "selected_option": str(option.public_id),
    }
    first = api_client.post("/api/v1/student-answers", payload, format="json")
    assert first.status_code == 201
    second = api_client.post("/api/v1/student-answers", payload, format="json")
    assert second.status_code == 409


@pytest.mark.django_db
def test_finalize_assessment_score_creates_result_from_answers(
    api_client, organization, user_factory, exam_fixture_set, assessment_factory,
    question_factory, question_option_factory, student_answer_factory,
):
    class_subject = exam_fixture_set["class_subject"]
    term = exam_fixture_set["term"]
    student = exam_fixture_set["student"]
    assessment = assessment_factory(class_subject=class_subject, term=term, max_score="30.00")
    mcq = question_factory(assessment=assessment, question_type="multiple_choice", marks="10.00", sequence=1)
    correct_option = question_option_factory(question=mcq, is_correct=True, sequence=1)
    student_answer_factory(
        question=mcq, student=student, selected_option=correct_option, is_correct=True,
        marks_awarded="10.00",
    )
    essay = question_factory(assessment=assessment, question_type="essay", marks="20.00", sequence=2)
    student_answer_factory(
        question=essay, student=student, text_answer="Some answer", marks_awarded="8.00",
    )

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "results.finalize", "results.view")
    _login(api_client, "a@example.com", "s3cret-pass!")

    resp = api_client.post(
        f"/api/v1/assessments/{assessment.public_id}/finalize-score",
        {"student": str(student.public_id)},
        format="json",
    )
    assert resp.status_code == 200, resp.json()
    body = resp.json()["data"]
    assert body["score"] == "18.00"
    assert body["status"] == "entered"


@pytest.mark.django_db
def test_finalize_assessment_score_rejects_ungraded_subjective_answers(
    api_client, organization, user_factory, exam_fixture_set, assessment_factory,
    question_factory, student_answer_factory,
):
    class_subject = exam_fixture_set["class_subject"]
    term = exam_fixture_set["term"]
    student = exam_fixture_set["student"]
    assessment = assessment_factory(class_subject=class_subject, term=term)
    essay = question_factory(assessment=assessment, question_type="essay", marks="20.00", sequence=1)
    student_answer_factory(question=essay, student=student, text_answer="Ungraded answer")

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "results.finalize")
    _login(api_client, "a@example.com", "s3cret-pass!")

    resp = api_client.post(
        f"/api/v1/assessments/{assessment.public_id}/finalize-score",
        {"student": str(student.public_id)},
        format="json",
    )
    assert resp.status_code == 409
