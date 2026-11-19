"""Regression tests for tenant-scoped CBT import outbox publication."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.cbt.models import CBTImportJob, CBTImportOutboxEvent
from apps.cbt.tasks.imports import dispatch_pending_cbt_imports
from apps.tenancy.context import activate_organization


def _create_outbox(fs, user, *, status="pending", attempts=0, locked_at=None):
    organization = fs["school"].organization
    job = CBTImportJob.all_tenants.create(
        organization=organization,
        created_by=user,
        school=fs["school"],
        subject=fs["subject"],
        class_level=fs["class_level"],
        source_name="questions.csv",
        source_format="csv",
        storage_key="private/cbt-imports/test/questions.csv",
        source_sha256="a" * 64,
        source_size_bytes=128,
        idempotency_key=f"outbox-test-{timezone.now().timestamp()}",
        status="uploaded",
    )
    event = CBTImportOutboxEvent.all_tenants.create(
        organization=organization,
        job=job,
        event_type="extract_source",
        payload={"job_public_id": str(job.public_id)},
        status=status,
        attempts=attempts,
        available_at=timezone.now() - timedelta(seconds=1),
        locked_at=locked_at,
    )
    return job, event


@pytest.mark.django_db
def test_dispatch_publishes_event_and_marks_it_published(
    cbt_fixture_set, user_factory, monkeypatch
):
    fs = cbt_fixture_set
    user = user_factory(organization=fs["school"].organization)
    job, event = _create_outbox(fs, user)
    published = []

    monkeypatch.setattr(
        "apps.cbt.tasks.imports.extract_cbt_import_job.apply_async",
        lambda *, args, queue: published.append((args, queue)),
    )

    result = dispatch_pending_cbt_imports.run()

    activate_organization(fs["school"].organization_id)
    event.refresh_from_db()
    assert result["published"] == 1
    assert published == [([str(job.public_id), fs["school"].organization_id], "imports")]
    assert event.status == "published"
    assert event.attempts == 1
    assert event.locked_at is None
    assert event.published_at is not None
    activate_organization(None)


@pytest.mark.django_db
def test_broker_failure_schedules_bounded_retry_without_leaking_exception(
    cbt_fixture_set, user_factory, monkeypatch
):
    fs = cbt_fixture_set
    user = user_factory(organization=fs["school"].organization)
    _, event = _create_outbox(fs, user)

    def fail_publish(*, args, queue):
        raise RuntimeError("redis://secret-password@broker/private")

    monkeypatch.setattr(
        "apps.cbt.tasks.imports.extract_cbt_import_job.apply_async",
        fail_publish,
    )

    result = dispatch_pending_cbt_imports.run()

    activate_organization(fs["school"].organization_id)
    event.refresh_from_db()
    assert result["retry_scheduled"] == 1
    assert event.status == "pending"
    assert event.attempts == 1
    assert event.available_at > timezone.now()
    assert event.last_error == "BROKER_PUBLISH_FAILED"
    assert "secret-password" not in event.last_error
    activate_organization(None)


@pytest.mark.django_db
def test_stale_publishing_lease_is_reclaimed_and_dispatched(
    cbt_fixture_set, user_factory, monkeypatch
):
    fs = cbt_fixture_set
    user = user_factory(organization=fs["school"].organization)
    job, event = _create_outbox(
        fs,
        user,
        status="publishing",
        attempts=1,
        locked_at=timezone.now() - timedelta(minutes=6),
    )
    published = []
    monkeypatch.setattr(
        "apps.cbt.tasks.imports.extract_cbt_import_job.apply_async",
        lambda *, args, queue: published.append(args),
    )

    result = dispatch_pending_cbt_imports.run()

    activate_organization(fs["school"].organization_id)
    event.refresh_from_db()
    assert result["published"] == 1
    assert published == [[str(job.public_id), fs["school"].organization_id]]
    assert event.status == "published"
    assert event.attempts == 2
    activate_organization(None)


@pytest.mark.django_db
def test_exhausted_publish_attempts_are_marked_failed(
    cbt_fixture_set, user_factory, monkeypatch
):
    fs = cbt_fixture_set
    user = user_factory(organization=fs["school"].organization)
    _, event = _create_outbox(fs, user, attempts=7)
    monkeypatch.setattr(
        "apps.cbt.tasks.imports.extract_cbt_import_job.apply_async",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("broker unavailable")),
    )

    result = dispatch_pending_cbt_imports.run()

    activate_organization(fs["school"].organization_id)
    event.refresh_from_db()
    assert result["failed"] == 1
    assert event.status == "failed"
    assert event.attempts == 8
    assert event.last_error == "BROKER_PUBLISH_FAILED"
    activate_organization(None)
