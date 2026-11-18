"""API tests for the tenant-scoped, read-only CBT import preview."""
import pytest

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.cbt.models import CBTImportIssue, CBTImportItem, CBTImportJob


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


def _job(fs, user):
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
        source_sha256="a" * 64,
        source_size_bytes=128,
        idempotency_key=f"preview-{user.pk}",
        status="validating",
    )


@pytest.mark.django_db
def test_import_preview_returns_paginated_items_and_safe_diagnostics(
    api_client, cbt_fixture_set, user_factory
):
    fs = cbt_fixture_set
    user = user_factory(
        organization=fs["school"].organization, email="preview@example.com", password="secret-pass!"
    )
    _grant(user, "cbt_questions.view")
    _login(api_client, "preview@example.com", "secret-pass!")
    job = _job(fs, user)

    for sequence in range(1, 4):
        item = CBTImportItem.objects.create(
            organization=job.organization,
            job=job,
            sequence=sequence,
            source_locator={"row": sequence + 1},
            source_fingerprint=str(sequence) * 64,
            payload={"text": f"Question {sequence}", "correct": "A"},
            validation_status="invalid" if sequence == 2 else "valid",
        )
        if sequence == 2:
            CBTImportIssue.objects.create(
                organization=job.organization,
                job=job,
                item=item,
                severity="error",
                code="ROW_VALIDATION_FAILED",
                message="option_b is missing",
                source_locator={"row": 3},
            )

    response = api_client.get(f"/api/v1/cbt/import-jobs/{job.public_id}/preview?page=2&page_size=2")
    assert response.status_code == 200, response.json()
    data = response.json()["data"]
    assert [item["sequence"] for item in data["items"]] == [3]
    assert data["pagination"] == {
        "page": 2, "page_size": 2, "total_items": 3, "total_pages": 2
    }
    assert "storage_key" not in data["job"]
    assert "source_sha256" not in data["job"]


@pytest.mark.django_db
def test_import_preview_is_tenant_scoped_and_requires_view_permission(
    api_client, cbt_fixture_set, user_factory, other_organization
):
    fs = cbt_fixture_set
    owner = user_factory(
        organization=fs["school"].organization, email="preview-owner@example.com", password="secret-pass!"
    )
    job = _job(fs, owner)
    outsider = user_factory(
        organization=other_organization, email="preview-outsider@example.com", password="secret-pass!"
    )
    _grant(outsider, "cbt_questions.view")
    _login(api_client, "preview-outsider@example.com", "secret-pass!")

    response = api_client.get(f"/api/v1/cbt/import-jobs/{job.public_id}/preview")
    assert response.status_code == 404


@pytest.mark.django_db
def test_import_preview_rejects_invalid_pagination(api_client, cbt_fixture_set, user_factory):
    fs = cbt_fixture_set
    user = user_factory(
        organization=fs["school"].organization, email="preview-page@example.com", password="secret-pass!"
    )
    _grant(user, "cbt_questions.view")
    _login(api_client, "preview-page@example.com", "secret-pass!")
    job = _job(fs, user)

    response = api_client.get(f"/api/v1/cbt/import-jobs/{job.public_id}/preview?page=0")
    assert response.status_code == 400
