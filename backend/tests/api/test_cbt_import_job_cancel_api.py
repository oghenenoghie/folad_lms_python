"""API tests for safe, tenant-scoped CBT import cancellation."""

import pytest
from django.db import connection

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.cbt.models import CBTImportJob


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


def _job(fs, user, *, status="uploaded"):
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
        source_sha256="c" * 64,
        source_size_bytes=128,
        idempotency_key=f"cancel-{user.pk}-{status}",
        status=status,
    )


@pytest.mark.django_db
def test_staff_can_cancel_uploaded_import_without_deleting_source(
    api_client, cbt_fixture_set, user_factory
):
    fs = cbt_fixture_set
    user = user_factory(
        organization=fs["school"].organization,
        email="cancel-import@example.com",
        password="secret-pass!",
    )
    _grant(user, "cbt_questions.create")
    _login(api_client, "cancel-import@example.com", "secret-pass!")
    job = _job(fs, user)

    response = api_client.post(
        f"/api/v1/cbt/import-jobs/{job.public_id}/cancel", {}, format="json"
    )

    assert response.status_code == 200, response.json()
    job.refresh_from_db()
    assert job.status == "cancelled"
    assert job.completed_at is not None
    assert job.updated_by_id == user.pk
    assert job.storage_key == "private/import-source"


@pytest.mark.django_db
def test_completed_import_cannot_be_cancelled(api_client, cbt_fixture_set, user_factory):
    fs = cbt_fixture_set
    user = user_factory(
        organization=fs["school"].organization,
        email="cancel-completed@example.com",
        password="secret-pass!",
    )
    _grant(user, "cbt_questions.create")
    _login(api_client, "cancel-completed@example.com", "secret-pass!")
    job = _job(fs, user, status="completed")

    response = api_client.post(
        f"/api/v1/cbt/import-jobs/{job.public_id}/cancel", {}, format="json"
    )

    assert response.status_code == 409
    job.refresh_from_db()
    assert job.status == "completed"


@pytest.mark.django_db
def test_import_cancellation_is_tenant_scoped(
    api_client, cbt_fixture_set, user_factory, other_organization
):
    fs = cbt_fixture_set
    owner = user_factory(
        organization=fs["school"].organization,
        email="cancel-owner@example.com",
        password="secret-pass!",
    )
    job = _job(fs, owner)
    outsider = user_factory(
        organization=other_organization,
        email="cancel-outsider@example.com",
        password="secret-pass!",
    )
    _grant(outsider, "cbt_questions.create")
    _login(api_client, "cancel-outsider@example.com", "secret-pass!")

    response = api_client.post(
        f"/api/v1/cbt/import-jobs/{job.public_id}/cancel", {}, format="json"
    )

    assert response.status_code == 404

    # Restore the owning tenant database context before asserting the row state.
    # all_tenants bypasses the ORM manager filter, but PostgreSQL RLS remains active.
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.current_org', %s, true)", [str(fs["school"].organization_id)])
        cursor.execute("SELECT set_config('app.platform_mode', 'false', true)")
    assert CBTImportJob.all_tenants.filter(pk=job.pk, status="uploaded").exists()


@pytest.mark.django_db
def test_import_cancellation_requires_create_permission(api_client, cbt_fixture_set, user_factory):
    fs = cbt_fixture_set
    user = user_factory(
        organization=fs["school"].organization,
        email="cancel-forbidden@example.com",
        password="secret-pass!",
    )
    _login(api_client, "cancel-forbidden@example.com", "secret-pass!")
    job = _job(fs, user)

    response = api_client.post(
        f"/api/v1/cbt/import-jobs/{job.public_id}/cancel", {}, format="json"
    )

    assert response.status_code == 403
    job.refresh_from_db()
    assert job.status == "uploaded"
