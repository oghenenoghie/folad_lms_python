import pytest

from apps.cbt.models import CBTImportItem, CBTImportJob, CBTImportIssue
from apps.cbt.services.import_extraction_service import extract_import_job
from apps.tenancy.context import activate_organization


def _create_job(*, fs, actor, key, source_format="csv"):
    organization = fs["subject"].organization
    return CBTImportJob.all_tenants.create(
        organization=organization,
        created_by=actor,
        school=fs["school"],
        subject=fs["subject"],
        class_level=fs["class_level"],
        source_name=f"questions.{source_format}",
        source_format=source_format,
        storage_key="private/source",
        source_sha256="a" * 64,
        source_size_bytes=200,
        idempotency_key=key,
    )


@pytest.mark.django_db
def test_extract_csv_persists_valid_and_invalid_items_without_questions(
    cbt_fixture_set, user_factory, monkeypatch
):
    fs = cbt_fixture_set
    organization = fs["subject"].organization
    actor = user_factory(organization=organization)
    job = _create_job(fs=fs, actor=actor, key="extract-csv-test")
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
    job = _create_job(fs=fs, actor=actor, key="extract-csv-replay")
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


@pytest.mark.django_db
def test_extract_persists_original_source_row_numbers_and_fingerprint(
    cbt_fixture_set, user_factory, monkeypatch
):
    fs = cbt_fixture_set
    organization = fs["subject"].organization
    actor = user_factory(organization=organization)
    job = _create_job(fs=fs, actor=actor, key="source-locator-test")
    source = (
        b"text,correct,option_a,option_b\n"
        b"First question?,A,One,Two\n"
        b",,,\n"
        b"Second question?,B,Three,Four\n"
    )
    monkeypatch.setattr("apps.core.storage.get_file_bytes", lambda key: source)
    activate_organization(organization.id)

    extract_import_job(job_id=job.pk, organization=organization, actor=actor)

    items = list(CBTImportItem.objects.filter(job=job).order_by("sequence"))
    assert [item.sequence for item in items] == [1, 2]
    assert [item.source_locator for item in items] == [{"row": 2}, {"row": 4}]
    assert items[0].source_fingerprint != items[1].source_fingerprint


@pytest.mark.django_db
def test_extract_xlsx_persists_actual_sheet_and_row_locator(
    cbt_fixture_set, user_factory, monkeypatch
):
    from io import BytesIO

    from openpyxl import Workbook

    fs = cbt_fixture_set
    organization = fs["subject"].organization
    actor = user_factory(organization=organization)
    job = _create_job(fs=fs, actor=actor, key="source-xlsx-locator", source_format="xlsx")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Imported Questions"
    sheet.append(["text", "correct", "option_a", "option_b"])
    sheet.append(["First question?", "A", "One", "Two"])
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    monkeypatch.setattr("apps.core.storage.get_file_bytes", lambda key: stream.getvalue())
    activate_organization(organization.id)

    extract_import_job(job_id=job.pk, organization=organization, actor=actor)

    item = CBTImportItem.objects.get(job=job)
    assert item.source_locator == {"row": 2, "sheet": "Imported Questions"}
