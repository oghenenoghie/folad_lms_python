import pytest

from apps.cbt.models import CBTImportItem, CBTImportJob, CBTImportIssue
from apps.cbt.services.import_extraction_service import extract_import_job
from apps.tenancy.context import activate_organization


@pytest.mark.django_db
def test_extract_csv_persists_valid_and_invalid_items_without_questions(
    cbt_fixture_set, user_factory, monkeypatch
):
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
        storage_key="private/source.csv",
        source_sha256="a" * 64,
        source_size_bytes=200,
        idempotency_key="extract-csv-test",
    )
    source = (
        b"text,correct,option_a,option_b,question_type\n"
        b"What is 2+2?,A,4,5,single_choice\n"
        b"Which is missing?,Z,Yes,No,single_choice\n"
    )
    monkeypatch.setattr("apps.core.storage.get_file_bytes", lambda key: source)
    activate_organization(organization.id)

    summary = extract_import_job(job_id=job.pk, organization=organization, actor=actor)

    assert summary == {
        "items_total": 2,
        "items_valid": 1,
        "items_invalid": 1,
        "items_committed": 0,
        "preview_only": True,
    }
    job.refresh_from_db()
    assert job.status == "validating"
    assert job.summary == summary
    assert CBTImportItem.objects.filter(job=job, validation_status="valid").count() == 1
    assert CBTImportItem.objects.filter(job=job, validation_status="invalid").count() == 1
    assert CBTImportIssue.objects.filter(job=job, code="ROW_VALIDATION_FAILED").count() == 1
    from apps.cbt.models import Question
    assert not Question.objects.filter(organization=organization).exists()


@pytest.mark.django_db
def test_extract_csv_replay_is_idempotent(cbt_fixture_set, user_factory, monkeypatch):
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
        storage_key="private/source.csv",
        source_sha256="b" * 64,
        source_size_bytes=100,
        idempotency_key="extract-csv-replay",
    )
    monkeypatch.setattr(
        "apps.core.storage.get_file_bytes",
        lambda key: b"text,correct,option_a,option_b\nQuestion?,A,One,Two\n",
    )
    activate_organization(organization.id)

    first = extract_import_job(job_id=job.pk, organization=organization, actor=actor)
    second = extract_import_job(job_id=job.pk, organization=organization, actor=actor)

    assert first == second
    assert CBTImportItem.objects.filter(job=job).count() == 1
    assert CBTImportIssue.objects.filter(job=job).count() == 0
