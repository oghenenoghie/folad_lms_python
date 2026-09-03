import io
import zipfile
from unittest.mock import patch

import pytest

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.report_cards.services import report_card_bulk_export_service


def _grant(user, *codes):
    role = Role.objects.create(name=f"ROLE_{user.pk}_{'_'.join(codes)}"[:100], label="Test Role")
    for code in codes:
        RolePermission.objects.create(role=role, permission=Permission.objects.get(code=code))
    UserRole.objects.create(user=user, role=role)


def _login(api_client, email, password):
    resp = api_client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    token = resp.json()["data"]["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


@pytest.mark.django_db
def test_run_bulk_export_generates_report_cards_and_uploads_a_zip(
    organization, report_card_fixture_set, assessment_factory, result_factory, report_card_bulk_export_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="80.00", status="published")

    export = report_card_bulk_export_factory(term=fs["term"])
    captured = {}

    def fake_save_file(*, key_prefix, filename, content, content_type):
        captured["content"] = content
        captured["content_type"] = content_type
        return "https://example.com/export.zip"

    with patch(
        "apps.report_cards.services.report_card_bulk_export_service.save_file", side_effect=fake_save_file
    ):
        report_card_bulk_export_service.run_bulk_export(export=export)

    export.refresh_from_db()
    assert export.status == "ready"
    assert export.file_url == "https://example.com/export.zip"
    assert export.report_card_count == 1
    assert export.failed_count == 0
    assert export.started_at is not None
    assert export.completed_at is not None
    assert captured["content_type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(captured["content"])) as zip_file:
        names = zip_file.namelist()
        assert len(names) == 1
        assert names[0].startswith("RC-")
        assert zip_file.read(names[0]).startswith(b"%PDF")


@pytest.mark.django_db
def test_run_bulk_export_scoped_to_one_class_arm_excludes_other_arms(
    organization, report_card_fixture_set, assessment_factory, result_factory, report_card_bulk_export_factory,
    class_arm_factory, student_factory, enrollment_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="80.00", status="published")

    other_class_arm = class_arm_factory(class_level=fs["class_arm"].class_level, name="B")
    other_student = student_factory(school=fs["school"], admission_number="A002")
    enrollment_factory(student=other_student, class_arm=other_class_arm, academic_year=fs["academic_year"])

    export = report_card_bulk_export_factory(term=fs["term"], class_arm=fs["class_arm"])

    with patch(
        "apps.report_cards.services.report_card_bulk_export_service.save_file",
        return_value="https://example.com/export.zip",
    ):
        report_card_bulk_export_service.run_bulk_export(export=export)

    export.refresh_from_db()
    assert export.status == "ready"
    assert export.report_card_count == 1


@pytest.mark.django_db
def test_run_bulk_export_marks_failed_on_exception(organization, report_card_fixture_set, report_card_bulk_export_factory):
    export = report_card_bulk_export_factory(term=report_card_fixture_set["term"])

    with patch(
        "apps.report_cards.services.report_card_service.generate_report_cards_bulk",
        side_effect=RuntimeError("boom"),
    ):
        report_card_bulk_export_service.run_bulk_export(export=export)

    export.refresh_from_db()
    assert export.status == "failed"
    assert "boom" in export.error_message


@pytest.mark.django_db(transaction=True)
def test_request_bulk_export_runs_on_commit_via_celery(
    organization, report_card_fixture_set, assessment_factory, result_factory,
):
    """transaction=True gives request_bulk_export's on_commit(...) call a
    real commit to fire on — same reasoning as test_report_cards_pdf.py's
    equivalent test for the single-report-card PDF job."""
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="80.00", status="published")

    with patch(
        "apps.report_cards.services.report_card_bulk_export_service.save_file",
        return_value="https://example.com/export.zip",
    ):
        export = report_card_bulk_export_service.request_bulk_export(term=fs["term"], actor=None)

    export.refresh_from_db()
    assert export.status == "ready"
    assert export.file_url == "https://example.com/export.zip"
    assert export.report_card_count == 1


@pytest.mark.django_db
def test_bulk_export_request_endpoint_creates_and_completes_an_export(
    api_client, organization, user_factory, report_card_fixture_set, assessment_factory, result_factory,
):
    """Plain (non-transactional) django_db, not transaction=True: this
    test needs the RBAC Permission rows seeded by report_cards'
    0002_seed_permissions migration, and transaction=True's underlying
    TransactionTestCase flushes migration-seeded data between tests
    unless serialized_rollback is on (it isn't here) — exactly the trap
    test_report_card_pdf_endpoint_redirects_once_ready_and_409s_before_
    that (test_report_cards_pdf.py) already sidesteps the same way: let
    on_commit's callback simply not fire (nothing here asserts on that —
    see test_request_bulk_export_runs_on_commit_via_celery for that), and
    call run_bulk_export directly afterward to stand in for the worker.
    """
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="80.00", status="published")

    user = user_factory(organization=organization, email="admin@example.com", password="s3cret-pass!")
    _grant(user, "report_cards.generate", "report_cards.view")
    _login(api_client, "admin@example.com", "s3cret-pass!")

    resp = api_client.post(
        "/api/v1/report-cards/bulk-exports/request",
        {"term": str(fs["term"].public_id)},
        format="json",
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "pending"
    public_id = data["public_id"]

    from apps.report_cards.models import ReportCardBulkExport

    export = ReportCardBulkExport.objects.get(public_id=public_id)
    with patch(
        "apps.report_cards.services.report_card_bulk_export_service.save_file",
        return_value="https://example.com/export.zip",
    ):
        report_card_bulk_export_service.run_bulk_export(export=export)

    detail = api_client.get(f"/api/v1/report-cards/bulk-exports/{public_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == "ready"

    listing = api_client.get("/api/v1/report-cards/bulk-exports")
    assert listing.status_code == 200
    assert any(row["public_id"] == public_id for row in listing.json()["data"]["results"])

    download = api_client.get(f"/api/v1/report-cards/bulk-exports/{public_id}/download")
    assert download.status_code == 302
    assert download.url == "https://example.com/export.zip"


@pytest.mark.django_db
def test_bulk_export_download_409s_before_ready(
    api_client, organization, user_factory, report_card_fixture_set, report_card_bulk_export_factory,
):
    user = user_factory(organization=organization, email="admin2@example.com", password="s3cret-pass!")
    _grant(user, "report_cards.view")
    _login(api_client, "admin2@example.com", "s3cret-pass!")

    export = report_card_bulk_export_factory(term=report_card_fixture_set["term"])

    resp = api_client.get(f"/api/v1/report-cards/bulk-exports/{export.public_id}/download")
    assert resp.status_code == 409


@pytest.mark.django_db
def test_bulk_export_request_requires_permission(
    api_client, organization, user_factory, report_card_fixture_set,
):
    user_factory(organization=organization, email="noperm@example.com", password="s3cret-pass!")
    _login(api_client, "noperm@example.com", "s3cret-pass!")

    resp = api_client.post(
        "/api/v1/report-cards/bulk-exports/request",
        {"term": str(report_card_fixture_set["term"].public_id)},
        format="json",
    )
    assert resp.status_code == 403
