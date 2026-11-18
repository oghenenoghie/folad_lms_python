"""API coverage for explicit, tenant-scoped CBT import commit."""
import pytest

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.cbt.models import CBTImportItem, CBTImportJob, Question


def _grant(user, *codes):
    role = Role.objects.create(name=f"ROLE_{user.pk}_{'_'.join(codes)}"[:100], label="Test Role")
    for code in codes:
        RolePermission.objects.create(role=role, permission=Permission.objects.get(code=code))
    UserRole.objects.create(user=user, role=role)


def _login(api_client, email, password):
    response = api_client.post(
        "/api/v1/auth/login", {"email": email, "password": password}, format="json"
    )
    assert response.status_code == 200, response.json()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['data']['access']}")


def _job(fs, user, *, status="validating"):
    return CBTImportJob.objects.create(
        organization=fs["school"].organization,
        created_by=user,
        updated_by=user,
        school=fs["school"],
        subject=fs["subject"],
        class_level=fs["class_level"],
        source_name="questions.csv",
        source_format="csv",
        storage_key="private/import-source",
        source_sha256="b" * 64,
        source_size_bytes=128,
        idempotency_key=f"commit-{user.pk}",
        status=status,
        summary={
            "items_total": 2,
            "items_valid": 2,
            "items_invalid": 0,
            "items_committed": 0,
            "preview_only": True,
        },
    )


def _item(job, sequence, *, valid=True):
    return CBTImportItem.objects.create(
        organization=job.organization,
        job=job,
        sequence=sequence,
        source_locator={"row": sequence + 1},
        source_fingerprint=str(sequence) * 64,
        payload={
            "text": f"Imported question {sequence}",
            "option_a": "First answer",
            "option_b": "Second answer",
            "correct": "A",
        },
        validation_status="valid" if valid else "invalid",
    )


@pytest.mark.django_db
def test_import_commit_creates_drafts_and_replay_is_idempotent(
    api_client, cbt_fixture_set, user_factory
):
    fs = cbt_fixture_set
    user = user_factory(
        organization=fs["school"].organization,
        email="commit-import@example.com",
        password="secret-pass!",
    )
    _grant(user, "cbt_questions.create")
    _login(api_client, "commit-import@example.com", "secret-pass!")
    job = _job(fs, user)
    first = _item(job, 1)
    second = _item(job, 2)

    url = f"/api/v1/cbt/import-jobs/{job.public_id}/commit"
    response = api_client.post(url, {}, format="json")
    assert response.status_code == 200, response.json()
    assert response.json()["data"]["status"] == "completed"
    assert response.json()["data"]["summary"]["items_committed"] == 2

    job.refresh_from_db()
    first.refresh_from_db()
    second.refresh_from_db()
    assert job.status == "completed"
    assert first.committed_question_id
    assert second.committed_question_id
    assert first.committed_question.status == "draft"
    assert second.committed_question.status == "draft"
    assert Question.objects.filter(
        organization=job.organization,
        blocks__content__html__startswith="Imported question",
    ).distinct().count() == 2

    replay = api_client.post(url, {}, format="json")
    assert replay.status_code == 200, replay.json()
    assert replay.json()["data"]["summary"]["items_committed"] == 2
    assert Question.objects.filter(
        organization=job.organization,
        blocks__content__html__startswith="Imported question",
    ).distinct().count() == 2


@pytest.mark.django_db
def test_import_commit_blocks_all_rows_when_any_item_is_invalid(
    api_client, cbt_fixture_set, user_factory
):
    fs = cbt_fixture_set
    user = user_factory(
        organization=fs["school"].organization,
        email="commit-invalid@example.com",
        password="secret-pass!",
    )
    _grant(user, "cbt_questions.create")
    _login(api_client, "commit-invalid@example.com", "secret-pass!")
    job = _job(fs, user)
    _item(job, 1)
    _item(job, 2, valid=False)

    response = api_client.post(
        f"/api/v1/cbt/import-jobs/{job.public_id}/commit", {}, format="json"
    )
    assert response.status_code == 409
    job.refresh_from_db()
    assert job.status == "validating"
    assert Question.objects.filter(organization=job.organization).count() == 0


@pytest.mark.django_db
def test_import_commit_is_tenant_scoped(
    api_client, cbt_fixture_set, user_factory, other_organization
):
    fs = cbt_fixture_set
    owner = user_factory(
        organization=fs["school"].organization,
        email="commit-owner@example.com",
        password="secret-pass!",
    )
    job = _job(fs, owner)
    outsider = user_factory(
        organization=other_organization,
        email="commit-outsider@example.com",
        password="secret-pass!",
    )
    _grant(outsider, "cbt_questions.create")
    _login(api_client, "commit-outsider@example.com", "secret-pass!")

    response = api_client.post(
        f"/api/v1/cbt/import-jobs/{job.public_id}/commit", {}, format="json"
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_import_commit_requires_create_permission(api_client, cbt_fixture_set, user_factory):
    fs = cbt_fixture_set
    user = user_factory(
        organization=fs["school"].organization,
        email="commit-forbidden@example.com",
        password="secret-pass!",
    )
    _login(api_client, "commit-forbidden@example.com", "secret-pass!")
    job = _job(fs, user)

    response = api_client.post(
        f"/api/v1/cbt/import-jobs/{job.public_id}/commit", {}, format="json"
    )
    assert response.status_code == 403
