import pytest
from django.db import IntegrityError, connection, transaction

from apps.cbt.models import CBTImportItem, CBTImportJob, CBTImportIssue
from apps.tenancy.context import activate_organization


@pytest.mark.django_db
def test_import_job_requires_actor_and_starts_uploaded(cbt_fixture_set, user_factory):
    fs = cbt_fixture_set
    actor = user_factory(organization=fs["subject"].organization)

    activate_organization(fs["subject"].organization_id)
    job = CBTImportJob.all_tenants.create(
        organization=fs["subject"].organization,
        created_by=actor,
        source_name="questions.xlsx",
        source_format="xlsx",
        storage_key=f"cbt-imports/{fs['subject'].organization_id}/source.xlsx",
        source_sha256="a" * 64,
        source_size_bytes=1024,
        idempotency_key="upload-request-001",
        subject=fs["subject"],
        class_level=fs["class_level"],
    )

    assert job.status == "uploaded"
    assert job.created_by_id == actor.pk
    assert job.items.count() == 0
    assert job.issues.count() == 0


@pytest.mark.django_db
def test_import_job_idempotency_key_is_unique_within_organization(
    cbt_fixture_set, user_factory
):
    fs = cbt_fixture_set
    actor = user_factory(organization=fs["subject"].organization)
    values = {
        "organization": fs["subject"].organization,
        "created_by": actor,
        "source_name": "questions.csv",
        "source_format": "csv",
        "storage_key": f"cbt-imports/{fs['subject'].organization_id}/source.csv",
        "source_sha256": "b" * 64,
        "source_size_bytes": 256,
        "idempotency_key": "same-request-key",
        "subject": fs["subject"],
        "class_level": fs["class_level"],
    }

    activate_organization(fs["subject"].organization_id)
    CBTImportJob.all_tenants.create(**values)
    with pytest.raises(IntegrityError), transaction.atomic():
        CBTImportJob.all_tenants.create(**values)


@pytest.mark.django_db
def test_import_item_has_unique_sequence_and_source_fingerprint(cbt_fixture_set, user_factory):
    fs = cbt_fixture_set
    actor = user_factory(organization=fs["subject"].organization)
    activate_organization(fs["subject"].organization_id)
    job = CBTImportJob.all_tenants.create(
        organization=fs["subject"].organization,
        created_by=actor,
        source_name="questions.xlsx",
        source_format="xlsx",
        storage_key=f"cbt-imports/{fs['subject'].organization_id}/source.xlsx",
        source_sha256="c" * 64,
        source_size_bytes=512,
        idempotency_key="item-constraints",
        subject=fs["subject"],
        class_level=fs["class_level"],
    )
    CBTImportItem.all_tenants.create(
        organization=fs["subject"].organization,
        job=job,
        sequence=1,
        source_locator={"sheet": "Questions", "row": 2},
        source_fingerprint="d" * 64,
        payload={"question_type": "single_choice"},
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        CBTImportItem.all_tenants.create(
            organization=fs["subject"].organization,
            job=job,
            sequence=1,
            source_fingerprint="e" * 64,
            payload={},
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        CBTImportItem.all_tenants.create(
            organization=fs["subject"].organization,
            job=job,
            sequence=2,
            source_fingerprint="d" * 64,
            payload={},
        )


@pytest.mark.django_db
def test_import_issue_preserves_job_item_provenance(cbt_fixture_set, user_factory):
    fs = cbt_fixture_set
    actor = user_factory(organization=fs["subject"].organization)
    activate_organization(fs["subject"].organization_id)
    job = CBTImportJob.all_tenants.create(
        organization=fs["subject"].organization,
        created_by=actor,
        source_name="questions.pdf",
        source_format="pdf",
        storage_key=f"cbt-imports/{fs['subject'].organization_id}/source.pdf",
        source_sha256="f" * 64,
        source_size_bytes=2048,
        idempotency_key="issue-provenance",
        subject=fs["subject"],
        class_level=fs["class_level"],
    )
    item = CBTImportItem.all_tenants.create(
        organization=fs["subject"].organization,
        job=job,
        sequence=1,
        source_locator={"page": 3, "paragraph": 4},
        source_fingerprint="1" * 64,
        payload={"blocks": []},
    )
    issue = CBTImportIssue.all_tenants.create(
        organization=fs["subject"].organization,
        job=job,
        item=item,
        severity="warning",
        code="ANSWER_KEY_MISSING",
        message="No explicit answer key was found in the source.",
        source_locator={"page": 3, "paragraph": 4},
    )

    assert issue.job_id == job.pk
    assert issue.item_id == item.pk
    assert issue.source_locator["page"] == 3


@pytest.mark.skipif(connection.vendor != "postgresql", reason="RLS is Postgres-only")
@pytest.mark.django_db
def test_import_job_rls_blocks_cross_tenant_raw_reads(
    cbt_fixture_set,
    other_organization,
    school_factory,
    campus_factory,
    class_level_factory,
    subject_factory,
    user_factory,
):
    fs_a = cbt_fixture_set
    school_b = school_factory(organization=other_organization, code="OTHER")
    class_level_b = class_level_factory(campus=campus_factory(school=school_b))
    subject_b = subject_factory(school=school_b)
    actor_a = user_factory(organization=fs_a["subject"].organization, email="import-a@example.com")
    actor_b = user_factory(organization=other_organization, email="import-b@example.com")

    def create_job(*, organization, actor, subject, class_level, key):
        activate_organization(organization.id)
        return CBTImportJob.all_tenants.create(
            organization=organization,
            created_by=actor,
            source_name="questions.csv",
            source_format="csv",
            storage_key=f"cbt-imports/{organization.id}/source.csv",
            source_sha256=key.ljust(64, "0"),
            source_size_bytes=128,
            idempotency_key=key,
            subject=subject,
            class_level=class_level,
        )

    create_job(
        organization=fs_a["subject"].organization,
        actor=actor_a,
        subject=fs_a["subject"],
        class_level=fs_a["class_level"],
        key="tenant-a",
    )
    create_job(
        organization=other_organization,
        actor=actor_b,
        subject=subject_b,
        class_level=class_level_b,
        key="tenant-b",
    )

    activate_organization(fs_a["subject"].organization_id)
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM cbt_import_job")
        (count,) = cursor.fetchone()

    assert count == 1


@pytest.mark.skipif(connection.vendor != "postgresql", reason="RLS is Postgres-only")
@pytest.mark.django_db
def test_import_job_rls_fails_closed_without_tenant_context(cbt_fixture_set, user_factory):
    fs = cbt_fixture_set
    actor = user_factory(organization=fs["subject"].organization)
    activate_organization(fs["subject"].organization_id)
    CBTImportJob.all_tenants.create(
        organization=fs["subject"].organization,
        created_by=actor,
        source_name="questions.csv",
        source_format="csv",
        storage_key=f"cbt-imports/{fs['subject'].organization_id}/source.csv",
        source_sha256="9" * 64,
        source_size_bytes=128,
        idempotency_key="sentinel-context",
        subject=fs["subject"],
        class_level=fs["class_level"],
    )

    activate_organization(None)
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM cbt_import_job")
        (count,) = cursor.fetchone()

    assert count == 0
