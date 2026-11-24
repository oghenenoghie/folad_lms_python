"""apps.cbt Phase 2: the DRF API surface on top of Phase 1's question-bank
models/service layer (backend/tests/api/test_cbt_questions.py already
covers that layer directly). These tests exercise the same behavior
through the actual HTTP endpoints: auth, permissions, nested block/option
sub-resources, the submit/approve/reject/duplicate workflow, media upload,
and tenant isolation.
"""
import pytest

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.cbt.models import QuestionBlock, QuestionVersion


def _grant(user, *codes):
    role = Role.objects.create(name=f"ROLE_{user.pk}_{'_'.join(codes)}"[:100], label="Test Role")
    for code in codes:
        RolePermission.objects.create(role=role, permission=Permission.objects.get(code=code))
    UserRole.objects.create(user=user, role=role)


def _login(api_client, email, password):
    resp = api_client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    token = resp.json()["data"]["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


@pytest.mark.django_db
def test_topic_crud_via_api(api_client, organization, user_factory, cbt_fixture_set):
    fs = cbt_fixture_set
    user = user_factory(organization=organization, email="admin@example.com", password="s3cret-pass!")
    _grant(user, "cbt_topics.view", "cbt_topics.create", "cbt_topics.update")
    _login(api_client, "admin@example.com", "s3cret-pass!")

    created = api_client.post(
        "/api/v1/cbt/topics", {"subject": str(fs["subject"].public_id), "name": "Algebra"}, format="json"
    )
    assert created.status_code == 201
    public_id = created.json()["data"]["public_id"]

    listed = api_client.get(f"/api/v1/cbt/topics?subject_id={fs['subject'].public_id}")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1

    updated = api_client.patch(f"/api/v1/cbt/topics/{public_id}", {"name": "Advanced Algebra"}, format="json")
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "Advanced Algebra"


@pytest.mark.django_db
def test_question_create_requires_permission(api_client, organization, user_factory, cbt_fixture_set):
    fs = cbt_fixture_set
    user_factory(organization=organization, email="norole@example.com", password="s3cret-pass!")
    _login(api_client, "norole@example.com", "s3cret-pass!")

    denied = api_client.post(
        "/api/v1/cbt/questions",
        {
            "subject": str(fs["subject"].public_id),
            "class_level": str(fs["class_level"].public_id),
            "question_type": "single_choice",
            "marks": "5.00",
        },
        format="json",
    )
    assert denied.status_code == 403


@pytest.mark.django_db
def test_question_create_and_filter_via_api(api_client, organization, user_factory, cbt_fixture_set):
    fs = cbt_fixture_set
    user = user_factory(organization=organization, email="teacher@example.com", password="s3cret-pass!")
    _grant(user, "cbt_questions.view", "cbt_questions.create")
    _login(api_client, "teacher@example.com", "s3cret-pass!")

    created = api_client.post(
        "/api/v1/cbt/questions",
        {
            "subject": str(fs["subject"].public_id),
            "class_level": str(fs["class_level"].public_id),
            "question_type": "numeric",
            "marks": "5.00",
        },
        format="json",
    )
    assert created.status_code == 201
    body = created.json()["data"]
    assert body["status"] == "draft"
    assert body["code"].startswith("Q-")

    filtered = api_client.get(f"/api/v1/cbt/questions?subject_id={fs['subject'].public_id}&status=draft")
    assert filtered.status_code == 200
    assert filtered.json()["data"]["pagination"]["total_count"] == 1

    empty = api_client.get(f"/api/v1/cbt/questions?subject_id={fs['subject'].public_id}&status=published")
    assert empty.json()["data"]["pagination"]["total_count"] == 0


@pytest.mark.django_db
def test_question_block_and_option_nested_endpoints(
    api_client, organization, user_factory, cbt_question_factory, cbt_fixture_set
):
    fs = cbt_fixture_set
    user = user_factory(organization=organization, email="teacher@example.com", password="s3cret-pass!")
    _grant(user, "cbt_questions.view", "cbt_questions.update")
    _login(api_client, "teacher@example.com", "s3cret-pass!")

    question = cbt_question_factory(subject=fs["subject"], class_level=fs["class_level"])

    bad_block = api_client.post(
        f"/api/v1/cbt/questions/{question.public_id}/blocks",
        {"block_type": "equation", "content": {}, "order": 1},
        format="json",
    )
    assert bad_block.status_code == 400

    block = api_client.post(
        f"/api/v1/cbt/questions/{question.public_id}/blocks",
        {"block_type": "equation", "content": {"latex": "x^2"}, "order": 1},
        format="json",
    )
    assert block.status_code == 201
    block_public_id = block.json()["data"]["public_id"]

    updated_block = api_client.patch(
        f"/api/v1/cbt/questions/{question.public_id}/blocks/{block_public_id}",
        {"content": {"latex": "y^2"}},
        format="json",
    )
    assert updated_block.status_code == 200
    assert updated_block.json()["data"]["content"]["latex"] == "y^2"

    option = api_client.post(
        f"/api/v1/cbt/questions/{question.public_id}/options",
        {"label": "A", "content": {"html": "42"}, "is_correct": True, "order": 1},
        format="json",
    )
    assert option.status_code == 201
    option_public_id = option.json()["data"]["public_id"]

    fetched = api_client.get(f"/api/v1/cbt/questions/{question.public_id}")
    assert fetched.status_code == 200
    assert len(fetched.json()["data"]["blocks"]) == 1
    assert len(fetched.json()["data"]["options"]) == 1

    deleted = api_client.delete(
        f"/api/v1/cbt/questions/{question.public_id}/options/{option_public_id}"
    )
    assert deleted.status_code == 200
    assert QuestionBlock.objects.filter(question=question).count() == 1


@pytest.mark.django_db
def test_question_workflow_via_api(
    api_client, organization, user_factory, cbt_question_factory, cbt_fixture_set
):
    fs = cbt_fixture_set
    author = user_factory(organization=organization, email="author@example.com", password="s3cret-pass!")
    _grant(author, "cbt_questions.view", "cbt_questions.submit", "cbt_questions.create")
    reviewer = user_factory(organization=organization, email="reviewer@example.com", password="s3cret-pass!")
    _grant(reviewer, "cbt_questions.view", "cbt_questions.approve")

    question = cbt_question_factory(subject=fs["subject"], class_level=fs["class_level"])

    _login(api_client, "author@example.com", "s3cret-pass!")
    submitted = api_client.post(f"/api/v1/cbt/questions/{question.public_id}/submit")
    assert submitted.status_code == 200
    assert submitted.json()["data"]["status"] == "submitted"

    denied_approve = api_client.post(f"/api/v1/cbt/questions/{question.public_id}/approve")
    assert denied_approve.status_code == 403

    _login(api_client, "reviewer@example.com", "s3cret-pass!")
    approved = api_client.post(f"/api/v1/cbt/questions/{question.public_id}/approve")
    assert approved.status_code == 200
    assert approved.json()["data"]["status"] == "approved"

    invalid_submit_again = api_client.post(f"/api/v1/cbt/questions/{question.public_id}/submit")
    assert invalid_submit_again.status_code == 403  # reviewer never got cbt_questions.submit

    _login(api_client, "author@example.com", "s3cret-pass!")
    duplicated = api_client.post(f"/api/v1/cbt/questions/{question.public_id}/duplicate")
    assert duplicated.status_code == 201
    assert duplicated.json()["data"]["status"] == "draft"
    assert duplicated.json()["data"]["public_id"] != str(question.public_id)


@pytest.mark.django_db
def test_reject_returns_conflict_from_a_terminal_state(
    api_client, organization, user_factory, cbt_question_factory, cbt_fixture_set
):
    fs = cbt_fixture_set
    user = user_factory(organization=organization, email="reviewer@example.com", password="s3cret-pass!")
    _grant(user, "cbt_questions.view", "cbt_questions.approve")
    _login(api_client, "reviewer@example.com", "s3cret-pass!")

    question = cbt_question_factory(subject=fs["subject"], class_level=fs["class_level"])  # still draft

    conflict = api_client.post(f"/api/v1/cbt/questions/{question.public_id}/reject")
    assert conflict.status_code == 409


@pytest.mark.django_db
def test_question_versions_endpoint_lists_snapshots_after_publish_edit(
    api_client, organization, user_factory, cbt_question_factory, cbt_fixture_set
):
    from apps.cbt.services.question_service import approve_question, publish_question, submit_question

    fs = cbt_fixture_set
    user = user_factory(organization=organization, email="admin@example.com", password="s3cret-pass!")
    _grant(user, "cbt_questions.view", "cbt_questions.update")

    question = cbt_question_factory(subject=fs["subject"], class_level=fs["class_level"], marks="4.00")
    submit_question(question=question, actor=None)
    approve_question(question=question, actor=None)
    publish_question(question=question, actor=None)

    _login(api_client, "admin@example.com", "s3cret-pass!")
    edited = api_client.patch(f"/api/v1/cbt/questions/{question.public_id}", {"marks": "6.00"}, format="json")
    assert edited.status_code == 200

    versions = api_client.get(f"/api/v1/cbt/questions/{question.public_id}/versions")
    assert versions.status_code == 200
    assert versions.json()["data"]["pagination"]["total_count"] == 1
    assert QuestionVersion.objects.get().content["marks"] == "4.00"


@pytest.mark.django_db
def test_media_upload_and_list_via_api(api_client, organization, user_factory):
    from django.core.files.uploadedfile import SimpleUploadedFile

    user = user_factory(organization=organization, email="admin@example.com", password="s3cret-pass!")
    _grant(user, "cbt_media.view", "cbt_media.upload")
    _login(api_client, "admin@example.com", "s3cret-pass!")

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 20
    upload = SimpleUploadedFile("diagram.png", png_bytes, content_type="image/png")

    uploaded = api_client.post(
        "/api/v1/cbt/media/upload",
        {"file": upload, "name": "Circuit diagram", "media_type": "image"},
        format="multipart",
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["data"]["download_url"]

    listed = api_client.get("/api/v1/cbt/media?media_type=image")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1


@pytest.mark.django_db
def test_cbt_api_tenant_isolation(
    api_client, organization, other_organization, user_factory, cbt_question_factory, cbt_fixture_set
):
    from apps.tenancy.context import activate_organization

    fs = cbt_fixture_set
    cbt_question_factory(subject=fs["subject"], class_level=fs["class_level"])

    other_user = user_factory(organization=other_organization, email="other@example.com", password="s3cret-pass!")
    activate_organization(other_organization.id)
    try:
        _grant(other_user, "cbt_questions.view")
    finally:
        activate_organization(organization.id)
    _login(api_client, "other@example.com", "s3cret-pass!")

    listed = api_client.get("/api/v1/cbt/questions")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 0
