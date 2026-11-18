"""Lifecycle and tenant-boundary tests for durable CBT import jobs."""
import pytest

from apps.cbt.models import CBTImportJob
from apps.cbt.services.import_job_service import (
    ImportJobError,
    InvalidImportJobTransition,
    transition_import_job,
)
from apps.tenancy.context import activate_organization


def _make_job(*, fs, actor, key="service-test"):
    organization = fs["subject"].organization
    return CBTImportJob.all_tenants.create(
        organization=organization,
        created_by=actor,
        school=fs["school"],
        subject=fs["subject"],
        class_level=fs["class_level"],
        source_name="questions.csv",
        source_format="csv",
        storage_key="private/import-source",
        source_sha256="a" * 64,
        source_size_bytes=128,
        idempotency_key=key,
    )


@pytest.mark.django_db
def test_import_job_lifecycle_records_start_completion_and_summary(cbt_fixture_set, user_factory):
    fs = cbt_fixture_set
    organization = fs["subject"].organization
    actor = user_factory(organization=organization)
    job = _make_job(fs=fs, actor=actor)
    activate_organization(organization.id)

    for status in ("queued", "extracting", "validating", "ready_to_commit", "committing"):
        job = transition_import_job(
            job_id=job.pk, organization=organization, to_status=status, actor=actor
        )

    assert job.started_at is not None
    assert job.completed_at is None

    job = transition_import_job(
        job_id=job.pk,
        organization=organization,
        to_status="completed",
        actor=actor,
        summary={"items_total": 12, "items_valid": 12},
    )
    assert job.status == "completed"
    assert job.completed_at is not None
    assert job.summary == {"items_total": 12, "items_valid": 12}
    assert job.updated_by_id == actor.pk


@pytest.mark.django_db
def test_import_job_same_status_is_idempotent(cbt_fixture_set, user_factory):
    fs = cbt_fixture_set
    organization = fs["subject"].organization
    actor = user_factory(organization=organization)
    job = _make_job(fs=fs, actor=actor, key="idempotent")
    activate_organization(organization.id)

    first = transition_import_job(
        job_id=job.pk, organization=organization, to_status="queued"
    )
    second = transition_import_job(
        job_id=job.pk, organization=organization, to_status="queued"
    )
    assert first.pk == second.pk
    assert second.status == "queued"
    assert second.started_at is None


@pytest.mark.django_db
def test_import_job_rejects_invalid_and_terminal_transitions(cbt_fixture_set, user_factory):
    fs = cbt_fixture_set
    organization = fs["subject"].organization
    actor = user_factory(organization=organization)
    job = _make_job(fs=fs, actor=actor, key="invalid-transition")
    activate_organization(organization.id)

    with pytest.raises(InvalidImportJobTransition):
        transition_import_job(
            job_id=job.pk, organization=organization, to_status="completed"
        )

    transition_import_job(
        job_id=job.pk, organization=organization, to_status="cancelled"
    )
    with pytest.raises(InvalidImportJobTransition):
        transition_import_job(
            job_id=job.pk, organization=organization, to_status="queued"
        )


@pytest.mark.django_db
def test_import_job_failure_records_safe_failure_metadata(cbt_fixture_set, user_factory):
    fs = cbt_fixture_set
    organization = fs["subject"].organization
    actor = user_factory(organization=organization)
    job = _make_job(fs=fs, actor=actor, key="failure")
    activate_organization(organization.id)

    transition_import_job(job_id=job.pk, organization=organization, to_status="queued")
    failed = transition_import_job(
        job_id=job.pk,
        organization=organization,
        to_status="failed",
        failure_code="PARSER_ERROR",
        failure_message="The source file could not be parsed.",
    )
    assert failed.status == "failed"
    assert failed.completed_at is not None
    assert failed.failure_code == "PARSER_ERROR"
    assert failed.failure_message == "The source file could not be parsed."


@pytest.mark.django_db
def test_import_job_cannot_be_transitioned_from_another_tenant(
    cbt_fixture_set, user_factory, other_organization
):
    fs = cbt_fixture_set
    organization = fs["subject"].organization
    actor = user_factory(organization=organization)
    job = _make_job(fs=fs, actor=actor, key="tenant-isolation")

    activate_organization(other_organization.id)
    with pytest.raises(CBTImportJob.DoesNotExist):
        transition_import_job(
            job_id=job.pk, organization=other_organization, to_status="queued"
        )


@pytest.mark.django_db
def test_import_job_failure_metadata_is_only_allowed_for_failed_status(
    cbt_fixture_set, user_factory
):
    fs = cbt_fixture_set
    organization = fs["subject"].organization
    actor = user_factory(organization=organization)
    job = _make_job(fs=fs, actor=actor, key="failure-metadata-guard")
    activate_organization(organization.id)

    with pytest.raises(ImportJobError):
        transition_import_job(
            job_id=job.pk,
            organization=organization,
            to_status="queued",
            failure_code="NOT_A_FAILURE",
        )
