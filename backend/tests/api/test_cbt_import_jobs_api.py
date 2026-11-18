"""API contract tests for private CBT source-import uploads."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.cbt.models import CBTImportJob


def _grant(user, *codes):
    role = Role.objects.create(name=f"ROLE_{user.pk}_{'_'.join(codes)}"[:100], label="Test Role")
    for code in codes:
        RolePermission.objects.create(role=role, permission=Permission.objects.get(code=code))
    UserRole.objects.create(user=user, role=role)


def _login(api_client, email, password):
    response = api_client.post(
        "/api/v1/auth/login",
        {"email": email, "password": password},
        format="json",
    )
    assert response.status_code == 200, response.json()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['data']['access']}")


def _upload(fs, content=b"text,correct,option_a,option_b\nWhat is 2+2?,B,3,4\n", name="questions.csv"):
    return {
        "file": SimpleUploadedFile(name, content, content_type="application/octet-stream"),
        "subject": str(fs["subject"].public_id),
        "class_level": str(fs["class_level"].public_id),
    }


@pytest.mark.django_db
def test_csv_upload_creates_private_uploaded_job_without_dispatch(
    api_client, cbt_fixture_set, user_factory, monkeypatch
):
    fs = cbt_fixture_set
    user = user_factory(organization=fs["school"].organization, email="importer@example.com", password="secret-pass!")
    _grant(user, "cbt_questions.create")
    _login(api_client, "importer@example.com", "secret-pass!")

    saved = []
    monkeypatch.setattr(
        "apps.core.storage.save_document",
        lambda **kwargs: saved.append(kwargs) or "private/cbt-import-source",
    )

    response = api_client.post(
        "/api/v1/cbt/import-jobs",
        _upload(fs),
        format="multipart",
        HTTP_IDEMPOTENCY_KEY="cbt-import-0001",
    )

    assert response.status_code == 201, response.json()
    data = response.json()["data"]
    job = CBTImportJob.objects.get(public_id=data["public_id"])
    assert job.status == "uploaded"
    assert job.storage_key == "private/cbt-import-source"
    assert job.source_format == "csv"
    assert job.source_size_bytes > 0
    assert data["processing_status"] == "not_configured"
    assert data["processing_dispatched"] is False
    assert "storage_key" not in data
    assert len(saved) == 1


@pytest.mark.django_db
def test_repeated_idempotent_upload_returns_same_job_without_second_storage_write(
    api_client, cbt_fixture_set, user_factory, monkeypatch
):
    fs = cbt_fixture_set
    user = user_factory(organization=fs["school"].organization, email="retry@example.com", password="secret-pass!")
    _grant(user, "cbt_questions.create")
    _login(api_client, "retry@example.com", "secret-pass!")

    saved = []
    monkeypatch.setattr(
        "apps.core.storage.save_document",
        lambda **kwargs: saved.append(kwargs) or f"private/source-{len(saved)}",
    )

    first = api_client.post(
        "/api/v1/cbt/import-jobs",
        _upload(fs),
        format="multipart",
        HTTP_IDEMPOTENCY_KEY="cbt-import-0002",
    )
    second = api_client.post(
        "/api/v1/cbt/import-jobs",
        _upload(fs),
        format="multipart",
        HTTP_IDEMPOTENCY_KEY="cbt-import-0002",
    )

    assert first.status_code == 201, first.json()
    assert second.status_code == 200, second.json()
    assert first.json()["data"]["public_id"] == second.json()["data"]["public_id"]
    assert len(saved) == 1
    assert CBTImportJob.objects.count() == 1


@pytest.mark.django_db
def test_idempotency_key_cannot_be_reused_for_different_source(
    api_client, cbt_fixture_set, user_factory, monkeypatch
):
    fs = cbt_fixture_set
    user = user_factory(organization=fs["school"].organization, email="conflict@example.com", password="secret-pass!")
    _grant(user, "cbt_questions.create")
    _login(api_client, "conflict@example.com", "secret-pass!")

    monkeypatch.setattr("apps.core.storage.save_document", lambda **kwargs: "private/source-key")

    first = api_client.post(
        "/api/v1/cbt/import-jobs",
        _upload(fs),
        format="multipart",
        HTTP_IDEMPOTENCY_KEY="cbt-import-0003",
    )
    second = api_client.post(
        "/api/v1/cbt/import-jobs",
        _upload(fs, content=b"text,correct,option_a,option_b\nWhat is 5+5?,A,10,11\n"),
        format="multipart",
        HTTP_IDEMPOTENCY_KEY="cbt-import-0003",
    )

    assert first.status_code == 201, first.json()
    assert second.status_code == 409, second.json()
    assert CBTImportJob.objects.count() == 1


@pytest.mark.django_db
def test_invalid_xlsx_bytes_are_rejected_before_storage(
    api_client, cbt_fixture_set, user_factory, monkeypatch
):
    fs = cbt_fixture_set
    user = user_factory(organization=fs["school"].organization, email="invalid@example.com", password="secret-pass!")
    _grant(user, "cbt_questions.create")
    _login(api_client, "invalid@example.com", "secret-pass!")

    saved = []
    monkeypatch.setattr(
        "apps.core.storage.save_document",
        lambda **kwargs: saved.append(kwargs) or "private/should-not-exist",
    )
    response = api_client.post(
        "/api/v1/cbt/import-jobs",
        _upload(fs, content=b"not an xlsx workbook", name="questions.xlsx"),
        format="multipart",
        HTTP_IDEMPOTENCY_KEY="cbt-import-0004",
    )

    assert response.status_code == 400, response.json()
    assert saved == []
    assert CBTImportJob.objects.count() == 0
