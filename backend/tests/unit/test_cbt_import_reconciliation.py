"""Regression tests for CBT import dispatch-to-worker reconciliation."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.cbt.models import CBTImportJob, CBTImportOutboxEvent
from apps.cbt.tasks.imports import reconcile_published_cbt_imports
from apps.tenancy.context import activate_organization


def _published_job(fs, user, *, job_status="uploaded", attempts=1):
    organization = fs["school"].organization
    job = CBTImportJob.all_tenants.create(
        organization=organization, created_by=user, school=fs["school"],
        subject=fs["subject"], class_level=fs["class_level"],
        source_name="questions.csv", source_format="csv",
        storage_key="private/cbt-imports/reconcile/questions.csv",
        source_sha256="b" * 64, source_size_bytes=128,
        idempotency_key=f"reconcile-{timezone.now().timestamp()}",
        status=job_status,
    )
    event = CBTImportOutboxEvent.all_tenants.create(
        organization=organization, job=job, event_type="extract_source",
        payload={"job_public_id": str(job.public_id)}, status="published",
        attempts=attempts, available_at=timezone.now() - timedelta(minutes=12),
        published_at=timezone.now() - timedelta(minutes=11),
    )
    return job, event


@pytest.mark.django_db
def test_reconciler_requeues_published_event_when_worker_never_starts(cbt_fixture_set, user_factory):
    fs = cbt_fixture_set
    user = user_factory(organization=fs["school"].organization)
    job, event = _published_job(fs, user)

    result = reconcile_published_cbt_imports.run()

    activate_organization(fs["school"].organization_id)
    event.refresh_from_db()
    assert result["requeued"] == 1
    assert event.status == "pending"
    assert event.published_at is None
    assert event.last_error == "WORKER_START_NOT_CONFIRMED"
    assert job.status == "uploaded"
    activate_organization(None)


@pytest.mark.django_db
def test_reconciler_does_not_requeue_cancelled_import(cbt_fixture_set, user_factory):
    fs = cbt_fixture_set
    user = user_factory(organization=fs["school"].organization)
    job, event = _published_job(fs, user, job_status="cancelled")

    result = reconcile_published_cbt_imports.run()

    activate_organization(fs["school"].organization_id)
    event.refresh_from_db()
    job.refresh_from_db()
    assert result["requeued"] == 0
    assert event.status == "published"
    assert job.status == "cancelled"
    activate_organization(None)


@pytest.mark.django_db
def test_reconciler_fails_job_after_dispatch_attempt_budget_is_exhausted(cbt_fixture_set, user_factory):
    fs = cbt_fixture_set
    user = user_factory(organization=fs["school"].organization)
    job, event = _published_job(fs, user, attempts=8)

    result = reconcile_published_cbt_imports.run()

    activate_organization(fs["school"].organization_id)
    event.refresh_from_db()
    job.refresh_from_db()
    assert result["failed"] == 1
    assert event.status == "failed"
    assert event.last_error == "MAX_DISPATCH_ATTEMPTS_EXCEEDED"
    assert job.status == "failed"
    assert job.failure_code == "DISPATCH_FAILED"
    assert "could not be scheduled" in job.failure_message
    activate_organization(None)