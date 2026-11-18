"""Tests for the CBT source-retention management command."""
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.cbt.models import CBTImportJob


def _terminal_job(fs, user, *, status="completed", age_days=31):
    return CBTImportJob.objects.create(
        organization=fs["school"].organization,
        created_by=user,
        updated_by=user,
        school=fs["school"],
        subject=fs["subject"],
        class_level=fs["class_level"],
        source_name="questions.csv",
        source_format="csv",
        storage_key=f"private/import-{user.pk}-{status}",
        source_sha256="d" * 64,
        source_size_bytes=128,
        idempotency_key=f"retention-{user.pk}-{status}",
        status=status,
        completed_at=timezone.now() - timedelta(days=age_days),
    )


@pytest.mark.django_db
def test_retention_command_is_dry_run_by_default(cbt_fixture_set, user_factory, monkeypatch):
    fs = cbt_fixture_set
    user = user_factory(organization=fs["school"].organization)
    job = _terminal_job(fs, user)
    deleted = []
    monkeypatch.setattr("apps.core.storage.delete_document", lambda key: deleted.append(key))
    output = StringIO()

    call_command("purge_cbt_import_sources", stdout=output)

    job.refresh_from_db()
    assert job.storage_key.startswith("private/")
    assert deleted == []
    assert "Dry run: 1 expired source(s) found; 0 deleted; 0 failed." in output.getvalue()


@pytest.mark.django_db
def test_retention_command_deletes_only_expired_terminal_sources(
    cbt_fixture_set, user_factory, monkeypatch
):
    fs = cbt_fixture_set
    user = user_factory(organization=fs["school"].organization)
    expired = _terminal_job(fs, user)
    recent = _terminal_job(fs, user_factory(organization=fs["school"].organization), age_days=5)
    active = CBTImportJob.objects.create(
        organization=fs["school"].organization,
        created_by=user,
        updated_by=user,
        school=fs["school"],
        subject=fs["subject"],
        class_level=fs["class_level"],
        source_name="active.csv",
        source_format="csv",
        storage_key="private/active",
        source_sha256="e" * 64,
        source_size_bytes=128,
        idempotency_key=f"retention-active-{user.pk}",
        status="validating",
        completed_at=timezone.now() - timedelta(days=45),
    )
    deleted = []
    monkeypatch.setattr("apps.core.storage.delete_document", lambda key: deleted.append(key))

    call_command("purge_cbt_import_sources", "--execute")

    expired.refresh_from_db()
    recent.refresh_from_db()
    active.refresh_from_db()
    assert expired.storage_key == ""
    assert deleted == [f"private/import-{user.pk}-completed"]
    assert recent.storage_key.startswith("private/")
    assert active.storage_key == "private/active"


@pytest.mark.django_db
def test_retention_command_keeps_key_when_storage_deletion_fails(cbt_fixture_set, user_factory, monkeypatch):
    fs = cbt_fixture_set
    user = user_factory(organization=fs["school"].organization)
    job = _terminal_job(fs, user)

    def fail_delete(key):
        raise OSError("storage unavailable")

    monkeypatch.setattr("apps.core.storage.delete_document", fail_delete)
    output = StringIO()
    errors = StringIO()

    call_command("purge_cbt_import_sources", "--execute", stdout=output, stderr=errors)

    job.refresh_from_db()
    assert job.storage_key.startswith("private/")
    assert "1 failed" in output.getvalue()
    assert "source deletion failed (OSError)" in errors.getvalue()
