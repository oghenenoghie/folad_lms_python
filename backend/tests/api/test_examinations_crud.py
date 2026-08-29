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
def test_report_card_generation_produces_pdf_via_celery(
    api_client, organization, user_factory, exam_fixture_set, assessment_factory, result_factory,
):
    class_subject = exam_fixture_set["class_subject"]
    term = exam_fixture_set["term"]
    student = exam_fixture_set["student"]
    assessment = assessment_factory(class_subject=class_subject, term=term)
    result_factory(assessment=assessment, student=student, status="published")

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "report_cards.create", "report_cards.view")
    _login(api_client, "a@example.com", "s3cret-pass!")

    created = api_client.post(
        "/api/v1/report-cards",
        {"student": str(student.public_id), "term": str(term.public_id)},
        format="json",
    )
    assert created.status_code == 201
    public_id = created.json()["data"]["public_id"]

    # CELERY_TASK_ALWAYS_EAGER runs the task synchronously inline above, so
    # generation has already completed by the time the response returns.
    retrieved = api_client.get(f"/api/v1/report-cards/{public_id}")
    body = retrieved.json()["data"]
    assert body["status"] == "ready"
    assert body["file_url"]
    assert body["generated_at"] is not None
