"""Atomicity, replay, and tenant-boundary tests for CBT import commits."""
import pytest

from apps.cbt.models import CBTImportItem, CBTImportJob, Question
from apps.cbt.services.import_commit_service import ImportCommitError, commit_import_job
from apps.tenancy.context import activate_organization


def _make_validated_job(*, fs, actor, key, rows=1):
    organization = fs["subject"].organization
    job = CBTImportJob.all_tenants.create(
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
        status="validating",
        summary={
            "items_total": rows,
            "items_valid": rows,
            "items_invalid": 0,
            "items_committed": 0,
            "preview_only": True,
        },
    )
    for sequence in range(1, rows + 1):
        CBTImportItem.all_tenants.create(
            organization=organization,
            job=job,
            sequence=sequence,
            source_locator={"row": sequence + 1},
            source_fingerprint=f"{sequence:064x}",
            payload={
                "text": f"Question {sequence}?",
                "correct": "A",
                "option_a": "Correct",
                "option_b": "Incorrect",
                "question_type": "single_choice",
            },
            validation_status="valid",
        )
    return job


@pytest.mark.django_db
def test_commit_creates_draft_questions_and_links_each_ledger_item(
    cbt_fixture_set, user_factory
):
    fs = cbt_fixture_set
    organization = fs["subject"].organization
    actor = user_factory(organization=organization)
    job = _make_validated_job(fs=fs, actor=actor, key="commit-success", rows=2)
    activate_organization(organization.id)

    summary = commit_import_job(job_id=job.pk, organization=organization, actor=actor)

    job.refresh_from_db()
    items = list(CBTImportItem.objects.filter(job=job).order_by("sequence"))
    questions = list(Question.objects.filter(organization=organization).order_by("pk"))
    assert job.status == "completed"
    assert summary["items_committed"] == 2
    assert summary["preview_only"] is False
    assert len(questions) == 2
    assert all(question.status == "draft" for question in questions)
    assert [item.committed_question_id for item in items] == [q.pk for q in questions]


@pytest.mark.django_db
def test_completed_commit_replay_does_not_create_duplicate_questions(
    cbt_fixture_set, user_factory
):
    fs = cbt_fixture_set
    organization = fs["subject"].organization
    actor = user_factory(organization=organization)
    job = _make_validated_job(fs=fs, actor=actor, key="commit-replay")
    activate_organization(organization.id)

    first = commit_import_job(job_id=job.pk, organization=organization, actor=actor)
    second = commit_import_job(job_id=job.pk, organization=organization, actor=actor)

    assert first == second
    assert Question.objects.filter(organization=organization).count() == 1
    assert CBTImportItem.objects.filter(job=job, committed_question__isnull=False).count() == 1


@pytest.mark.django_db
def test_invalid_or_pending_item_blocks_entire_commit(cbt_fixture_set, user_factory):
    fs = cbt_fixture_set
    organization = fs["subject"].organization
    actor = user_factory(organization=organization)
    job = _make_validated_job(fs=fs, actor=actor, key="commit-invalid", rows=2)
    CBTImportItem.all_tenants.filter(job=job, sequence=2).update(validation_status="invalid")
    activate_organization(organization.id)

    with pytest.raises(ImportCommitError, match="all rows must be valid"):
        commit_import_job(job_id=job.pk, organization=organization, actor=actor)

    job.refresh_from_db()
    assert job.status == "validating"
    assert Question.objects.filter(organization=organization).count() == 0


@pytest.mark.django_db
def test_failure_during_second_question_rolls_back_whole_commit(
    cbt_fixture_set, user_factory, monkeypatch
):
    from apps.cbt.services import import_commit_service

    fs = cbt_fixture_set
    organization = fs["subject"].organization
    actor = user_factory(organization=organization)
    job = _make_validated_job(fs=fs, actor=actor, key="commit-rollback", rows=2)
    activate_organization(organization.id)
    real_create_question = import_commit_service.create_question
    calls = 0

    def fail_on_second(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated database write failure")
        return real_create_question(**kwargs)

    monkeypatch.setattr(import_commit_service, "create_question", fail_on_second)

    with pytest.raises(RuntimeError, match="simulated database write failure"):
        commit_import_job(job_id=job.pk, organization=organization, actor=actor)

    job.refresh_from_db()
    assert job.status == "validating"
    assert Question.objects.filter(organization=organization).count() == 0
    assert CBTImportItem.objects.filter(job=job, committed_question__isnull=False).count() == 0


@pytest.mark.django_db
def test_commit_cannot_read_or_commit_another_tenants_job(
    cbt_fixture_set, user_factory, other_organization
):
    fs = cbt_fixture_set
    organization = fs["subject"].organization
    actor = user_factory(organization=organization)
    job = _make_validated_job(fs=fs, actor=actor, key="commit-tenant-boundary")
    activate_organization(other_organization.id)

    with pytest.raises(CBTImportJob.DoesNotExist):
        commit_import_job(job_id=job.pk, organization=other_organization, actor=actor)
