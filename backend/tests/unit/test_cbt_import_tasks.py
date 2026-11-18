"""Tests for tenant-safe, idempotent CBT import worker tasks."""
import pytest

from apps.cbt.models import CBTImportItem, CBTImportJob
from apps.cbt.tasks.imports import extract_cbt_import_job
from apps.tenancy.context import activate_organization


@pytest.fixture
def import_job(cbt_fixture_set, user_factory):
    fs = cbt_fixture_set
    organization = fs["school"].organization
    user = user_factory(organization=organization, email="worker-owner@example.com")
    activate_organization(organization.pk)
    return CBTImportJob.all_tenants.create(
        organization=organization,
        created_by=user,
        school=fs["school"],
        subject=fs["subject"],
        class_level=fs["class_level"],
        source_name="questions.csv",
        source_format="csv",
        storage_key="private/cbt-imports/source.csv",
        source_sha256="a" * 64,
        source_size_bytes=64,
        idempotency_key="worker-test-import",
    )


@pytest.mark.django_db
def test_worker_extracts_source_under_persisted_tenant_and_is_idempotent(
    import_job, monkeypatch
):
    from apps.tenancy.models import Organization

    content = b"text,correct,option_a,option_b\nWhat is 2+2?,B,3,4\n"
    monkeypatch.setattr("apps.core.storage.get_file_bytes", lambda key: content)

    first = extract_cbt_import_job.run(str(import_job.public_id), import_job.organization_id)
    second = extract_cbt_import_job.run(str(import_job.public_id), import_job.organization_id)

    activate_organization(import_job.organization_id)
    job = CBTImportJob.objects.get(pk=import_job.pk)
    assert Organization.objects.get(pk=job.organization_id).pk == job.organization_id
    assert first["status"] == "validating"
    assert second["status"] == "validating"
    assert second["summary"]["items_total"] == 1
    assert CBTImportItem.objects.filter(job=job).count() == 1
    assert job.status == "validating"


@pytest.mark.django_db
def test_worker_rejects_mismatched_tenant_locator_without_touching_job(
    import_job, other_organization, monkeypatch
):
    monkeypatch.setattr(
        "apps.core.storage.get_file_bytes",
        lambda key: pytest.fail("cross-tenant job must not read its source object"),
    )

    result = extract_cbt_import_job.run(str(import_job.public_id), other_organization.pk)

    assert result == {"status": "not_found"}
    activate_organization(import_job.organization_id)
    assert CBTImportJob.objects.get(pk=import_job.pk).status == "uploaded"


@pytest.mark.django_db
def test_worker_records_deterministic_extraction_failure_without_leaking_details(
    import_job, monkeypatch
):
    monkeypatch.setattr("apps.core.storage.get_file_bytes", lambda key: b"not,a,valid,question")

    result = extract_cbt_import_job.run(str(import_job.public_id), import_job.organization_id)

    activate_organization(import_job.organization_id)
    job = CBTImportJob.objects.get(pk=import_job.pk)
    assert result == {"status": "failed"}
    assert job.status == "failed"
    assert job.failure_code == "EXTRACTION_FAILED"
    assert "not,a,valid" not in job.failure_message


@pytest.mark.django_db
def test_worker_does_not_reopen_cancelled_job(import_job, monkeypatch):
    from apps.cbt.services.import_job_service import transition_import_job

    activate_organization(import_job.organization_id)
    transition_import_job(
        job_id=import_job.pk,
        organization=import_job.organization,
        to_status="cancelled",
    )
    monkeypatch.setattr(
        "apps.core.storage.get_file_bytes",
        lambda key: pytest.fail("cancelled jobs must not read source objects"),
    )

    result = extract_cbt_import_job.run(str(import_job.public_id), import_job.organization_id)

    assert result["status"] == "cancelled"
    activate_organization(import_job.organization_id)
    assert CBTImportJob.objects.get(pk=import_job.pk).status == "cancelled"
