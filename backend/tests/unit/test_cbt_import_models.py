"""Persistence and tenant-scope tests for durable CBT import jobs."""
import pytest
from django.db import IntegrityError, transaction

from apps.cbt.models import CBTImportIssue, CBTImportItem, CBTImportJob
from apps.tenancy.context import activate_organization, activate_platform_mode


@pytest.mark.django_db
def test_import_job_persists_private_source_metadata_and_target(cbt_fixture_set, user_factory):
    fs = cbt_fixture_set
    organization = fs["subject"].organization
    actor = user_factory(organization=organization)

    job = CBTImportJob.all_tenants.create(
        organization=organization,
        created_by=actor,
        school=fs["school"],
        subject=fs["subject"],
        class_level=fs["class_level"],
        source_name="questions.csv",
        source_format="csv",
        storage_key=f"cbt-imports/{organization.public_id}/opaque-object",
        source_sha256="a" * 64,
        source_size_bytes=512,
        idempotency_key="request-001",
    )

    assert job.status == "uploaded"
    assert job.storage_key.startswith(f"cbt-imports/{organization.public_id}/")
    assert job.subject_id == fs["subject"].id
    assert job.class_level_id == fs["class_level"].id


@pytest.mark.django_db
def test_import_job_idempotency_key_is_unique_per_organization(cbt_fixture_set, user_factory):
    fs = cbt_fixture_set
    organization = fs["subject"].organization
    actor = user_factory(organization=organization)
    values = dict(
        organization=organization,
        created_by=actor,
        school=fs["school"],
        subject=fs["subject"],
        class_level=fs["class_level"],
        source_name="questions.csv",
        source_format="csv",
        storage_key="private/key",
        source_sha256="b" * 64,
        source_size_bytes=10,
        idempotency_key="same-key",
    )
    CBTImportJob.all_tenants.create(**values)
    with pytest.raises(IntegrityError), transaction.atomic():
        CBTImportJob.all_tenants.create(**values)


@pytest.mark.django_db
def test_import_items_enforce_stable_sequence_and_fingerprint(cbt_fixture_set, user_factory):
    fs = cbt_fixture_set
    organization = fs["subject"].organization
    actor = user_factory(organization=organization)
    job = CBTImportJob.all_tenants.create(
        organization=organization,
        created_by=actor,
        school=fs["school"],
        subject=fs["subject"],
        class_level=fs["class_level"],
        source_name="questions.csv",
        source_format="csv",
        storage_key="private/key",
        source_sha256="c" * 64,
        source_size_bytes=10,
        idempotency_key="item-test",
    )
    item = CBTImportItem.all_tenants.create(
        organization=organization,
        job=job,
        sequence=1,
        source_locator={"row": 2},
        source_fingerprint="d" * 64,
        payload={"question_type": "single_choice"},
        validation_status="valid",
    )
    assert item.job_id == job.id
    assert job.items.count() == 1

    with pytest.raises(IntegrityError), transaction.atomic():
        CBTImportItem.all_tenants.create(
            organization=organization,
            job=job,
            sequence=2,
            source_fingerprint="d" * 64,
            payload={},
        )


@pytest.mark.django_db
def test_import_issue_can_be_job_level_or_item_level(cbt_fixture_set, user_factory):
    fs = cbt_fixture_set
    organization = fs["subject"].organization
    actor = user_factory(organization=organization)
    job = CBTImportJob.all_tenants.create(
        organization=organization,
        created_by=actor,
        school=fs["school"],
        subject=fs["subject"],
        class_level=fs["class_level"],
        source_name="questions.xlsx",
        source_format="xlsx",
        storage_key="private/key",
        source_sha256="e" * 64,
        source_size_bytes=10,
        idempotency_key="issue-test",
    )
    item = CBTImportItem.all_tenants.create(
        organization=organization,
        job=job,
        sequence=1,
        source_fingerprint="f" * 64,
        payload={},
    )
    job_issue = CBTImportIssue.all_tenants.create(
        organization=organization, job=job, severity="warning",
        code="SOURCE_WARNING", message="Workbook contains an empty row.",
    )
    item_issue = CBTImportIssue.all_tenants.create(
        organization=organization, job=job, item=item, severity="error",
        code="INVALID_ROW", message="Question stem is missing.",
        source_locator={"row": 4},
    )
    assert job_issue.item_id is None
    assert item_issue.item_id == item.id
    assert job.issues.count() == 2


@pytest.mark.django_db
def test_import_jobs_default_manager_is_tenant_scoped(cbt_fixture_set, user_factory, other_organization):
    fs = cbt_fixture_set
    organization = fs["subject"].organization
    actor = user_factory(organization=organization)
    CBTImportJob.all_tenants.create(
        organization=organization,
        created_by=actor,
        school=fs["school"],
        subject=fs["subject"],
        class_level=fs["class_level"],
        source_name="questions.csv",
        source_format="csv",
        storage_key="private/key",
        source_sha256="1" * 64,
        source_size_bytes=10,
        idempotency_key="tenant-scope",
    )

    # The explicit all_tenants manager can see the row before a database
    # tenant context is applied. PostgreSQL RLS still constrains even that
    # manager once a different organization is active; it is not an RLS bypass.
    assert CBTImportJob.all_tenants.count() == 1

    activate_organization(other_organization.id)
    assert CBTImportJob.objects.count() == 0
    # The unscoped manager bypasses TenantManager, but PostgreSQL RLS still applies.
    assert CBTImportJob.all_tenants.count() == 0

    # Cross-tenant visibility requires the audited platform-mode RLS bypass.
    activate_platform_mode()
    assert CBTImportJob.all_tenants.count() == 1
