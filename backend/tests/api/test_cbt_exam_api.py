"""apps.cbt Phase 3: the DRF API surface on top of exam_service
(backend/tests/api/test_cbt_exams.py already covers that layer directly).
"""
import pytest

from apps.accounts.models import Permission, Role, RolePermission, UserRole
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


def _approved_question(cbt_question_factory, fs, **extra):
    question = cbt_question_factory(subject=fs["subject"], class_level=fs["class_level"], **extra)
    submit_question(question=question, actor=None)
    approve_question(question=question, actor=None)
    return question


@pytest.mark.django_db
def test_exam_create_requires_permission(api_client, organization, user_factory, cbt_exam_fixture_set):
    fs = cbt_exam_fixture_set
    user_factory(organization=organization, email="norole@example.com", password="s3cret-pass!")
    _login(api_client, "norole@example.com", "s3cret-pass!")

    denied = api_client.post(
        "/api/v1/cbt/exams",
        {
            "school": str(fs["school"].public_id),
            "academic_year": str(fs["academic_year"].public_id),
            "term": str(fs["term"].public_id),
            "subject": str(fs["subject"].public_id),
            "class_level": str(fs["class_level"].public_id),
            "name": "First CA",
            "exam_type": "ca",
            "duration_minutes": 30,
            "pass_mark": "20.00",
            "start_at": "2025-09-15T09:00:00Z",
            "end_at": "2025-09-15T09:30:00Z",
        },
        format="json",
    )
    assert denied.status_code == 403


@pytest.mark.django_db
def test_exam_create_and_list_via_api(api_client, organization, user_factory, cbt_exam_fixture_set):
    fs = cbt_exam_fixture_set
    user = user_factory(organization=organization, email="admin@example.com", password="s3cret-pass!")
    _grant(user, "cbt_exams.view", "cbt_exams.create")
    _login(api_client, "admin@example.com", "s3cret-pass!")

    created = api_client.post(
        "/api/v1/cbt/exams",
        {
            "school": str(fs["school"].public_id),
            "academic_year": str(fs["academic_year"].public_id),
            "term": str(fs["term"].public_id),
            "subject": str(fs["subject"].public_id),
            "class_level": str(fs["class_level"].public_id),
            "name": "First CA",
            "exam_type": "ca",
            "duration_minutes": 30,
            "pass_mark": "20.00",
            "start_at": "2025-09-15T09:00:00Z",
            "end_at": "2025-09-15T09:30:00Z",
        },
        format="json",
    )
    assert created.status_code == 201, created.json()
    assert created.json()["data"]["code"].startswith("CBT-")
    assert created.json()["data"]["status"] == "draft"

    listed = api_client.get(f"/api/v1/cbt/exams?subject_id={fs['subject'].public_id}")
    assert listed.status_code == 200
    # fs["exam"] plus the one just created
    assert listed.json()["data"]["pagination"]["total_count"] == 2


@pytest.mark.django_db
def test_add_question_via_api_rejects_unapproved_question(
    api_client, organization, user_factory, cbt_exam_fixture_set, cbt_question_factory
):
    fs = cbt_exam_fixture_set
    user = user_factory(organization=organization, email="admin@example.com", password="s3cret-pass!")
    _grant(user, "cbt_exams.view", "cbt_exams.update")
    _login(api_client, "admin@example.com", "s3cret-pass!")

    draft_question = cbt_question_factory(subject=fs["subject"], class_level=fs["class_level"])
    rejected = api_client.post(
        f"/api/v1/cbt/exams/{fs['exam'].public_id}/questions",
        {"question": str(draft_question.public_id), "order": 1},
        format="json",
    )
    assert rejected.status_code == 409

    approved = _approved_question(cbt_question_factory, fs)
    added = api_client.post(
        f"/api/v1/cbt/exams/{fs['exam'].public_id}/questions",
        {"question": str(approved.public_id), "order": 1},
        format="json",
    )
    assert added.status_code == 201
    assert added.json()["data"]["snapshot"] == {}


@pytest.mark.django_db
def test_generate_questions_endpoint(
    api_client, organization, user_factory, cbt_exam_fixture_set, cbt_question_factory
):
    fs = cbt_exam_fixture_set
    user = user_factory(organization=organization, email="admin@example.com", password="s3cret-pass!")
    _grant(user, "cbt_exams.view", "cbt_exams.update")
    _login(api_client, "admin@example.com", "s3cret-pass!")

    for _ in range(3):
        _approved_question(cbt_question_factory, fs)

    generated = api_client.post(
        f"/api/v1/cbt/exams/{fs['exam'].public_id}/generate-questions",
        {
            "subject": str(fs["subject"].public_id),
            "class_level": str(fs["class_level"].public_id),
            "count": 2,
        },
        format="json",
    )
    assert generated.status_code == 201, generated.json()
    assert len(generated.json()["data"]) == 2


@pytest.mark.django_db
def test_candidate_bulk_add_from_class_arm_via_api(
    api_client, organization, user_factory, cbt_exam_fixture_set, student_factory, enrollment_factory
):
    fs = cbt_exam_fixture_set
    user = user_factory(organization=organization, email="admin@example.com", password="s3cret-pass!")
    _grant(user, "cbt_exam_candidates.view", "cbt_exam_candidates.manage")
    _login(api_client, "admin@example.com", "s3cret-pass!")

    student = student_factory(school=fs["school"])
    enrollment_factory(student=student, class_arm=fs["class_arm"], academic_year=fs["academic_year"])

    added = api_client.post(
        f"/api/v1/cbt/exams/{fs['exam'].public_id}/candidates/from-class-arm",
        {"class_arm": str(fs["class_arm"].public_id), "academic_year": str(fs["academic_year"].public_id)},
        format="json",
    )
    assert added.status_code == 201
    assert len(added.json()["data"]) == 1

    listed = api_client.get(f"/api/v1/cbt/exams/{fs['exam'].public_id}/candidates")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1


@pytest.mark.django_db
def test_publish_and_archive_workflow_via_api(
    api_client, organization, user_factory, cbt_exam_fixture_set, cbt_question_factory, student_factory
):
    fs = cbt_exam_fixture_set
    user = user_factory(organization=organization, email="admin@example.com", password="s3cret-pass!")
    _grant(
        user,
        "cbt_exams.view",
        "cbt_exams.update",
        "cbt_exams.publish",
        "cbt_exam_candidates.manage",
    )
    _login(api_client, "admin@example.com", "s3cret-pass!")

    question = _approved_question(cbt_question_factory, fs)
    api_client.post(
        f"/api/v1/cbt/exams/{fs['exam'].public_id}/questions",
        {"question": str(question.public_id), "order": 1},
        format="json",
    )
    student = student_factory(school=fs["school"])
    api_client.post(
        f"/api/v1/cbt/exams/{fs['exam'].public_id}/candidates",
        {"student": str(student.public_id)},
        format="json",
    )

    published = api_client.post(f"/api/v1/cbt/exams/{fs['exam'].public_id}/publish")
    assert published.status_code == 200
    assert published.json()["data"]["status"] == "published"
    assert published.json()["data"]["total_marks"] == "1.00"

    republish = api_client.post(f"/api/v1/cbt/exams/{fs['exam'].public_id}/publish")
    assert republish.status_code == 409

    edit_after_publish = api_client.patch(
        f"/api/v1/cbt/exams/{fs['exam'].public_id}", {"name": "Renamed"}, format="json"
    )
    assert edit_after_publish.status_code == 409

    archived = api_client.post(f"/api/v1/cbt/exams/{fs['exam'].public_id}/archive")
    assert archived.status_code == 200
    assert archived.json()["data"]["status"] == "archived"


@pytest.mark.django_db
def test_publish_without_questions_returns_400(
    api_client, organization, user_factory, cbt_exam_fixture_set
):
    user = user_factory(organization=organization, email="admin@example.com", password="s3cret-pass!")
    _grant(user, "cbt_exams.publish")
    _login(api_client, "admin@example.com", "s3cret-pass!")

    fs = cbt_exam_fixture_set
    resp = api_client.post(f"/api/v1/cbt/exams/{fs['exam'].public_id}/publish")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_reorder_exam_questions_via_api(
    api_client, organization, user_factory, cbt_exam_fixture_set, cbt_question_factory
):
    fs = cbt_exam_fixture_set
    user = user_factory(organization=organization, email="admin@example.com", password="s3cret-pass!")
    _grant(user, "cbt_exams.view", "cbt_exams.update")
    _login(api_client, "admin@example.com", "s3cret-pass!")

    q1 = _approved_question(cbt_question_factory, fs)
    q2 = _approved_question(cbt_question_factory, fs)
    r1 = api_client.post(
        f"/api/v1/cbt/exams/{fs['exam'].public_id}/questions",
        {"question": str(q1.public_id), "order": 1},
        format="json",
    ).json()["data"]
    r2 = api_client.post(
        f"/api/v1/cbt/exams/{fs['exam'].public_id}/questions",
        {"question": str(q2.public_id), "order": 2},
        format="json",
    ).json()["data"]

    reordered = api_client.post(
        f"/api/v1/cbt/exams/{fs['exam'].public_id}/questions/reorder",
        {"ordered_public_ids": [r2["public_id"], r1["public_id"]]},
        format="json",
    )
    assert reordered.status_code == 200
    orders = {row["public_id"]: row["order"] for row in reordered.json()["data"]}
    assert orders[r2["public_id"]] == 1
    assert orders[r1["public_id"]] == 2


@pytest.mark.django_db
def test_cbt_exam_api_tenant_isolation(
    api_client, organization, other_organization, user_factory, cbt_exam_fixture_set
):
    from apps.tenancy.context import activate_organization

    other_user = user_factory(organization=other_organization, email="other@example.com", password="s3cret-pass!")
    activate_organization(other_organization.id)
    try:
        _grant(other_user, "cbt_exams.view")
    finally:
        activate_organization(organization.id)
    _login(api_client, "other@example.com", "s3cret-pass!")

    listed = api_client.get("/api/v1/cbt/exams")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 0
