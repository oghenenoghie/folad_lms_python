import pytest

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.report_cards.services.report_card_pdf_service import render_report_card_pdf
from apps.report_cards.services.report_card_service import generate_report_card


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
def test_render_report_card_pdf_produces_a_real_pdf(
    organization, report_card_fixture_set, assessment_factory, result_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="75.00", status="published")

    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)
    pdf_bytes = render_report_card_pdf(report_card)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


@pytest.mark.django_db(transaction=True)
def test_generate_report_card_enqueues_pdf_rendering_on_commit(
    organization, report_card_fixture_set, assessment_factory, result_factory,
):
    """transaction=True gives generate_report_card's own @transaction.atomic
    a real outermost transaction to commit (rather than nesting inside
    pytest-django's default per-test rollback-only wrapper), so its
    on_commit(...) callback fires natively the moment the function
    returns — no django_capture_on_commit_callbacks needed."""
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="82.00", status="published")

    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)

    report_card.refresh_from_db()
    assert report_card.pdf_status == "ready"
    assert report_card.pdf_file_url
    assert report_card.pdf_generated_at is not None
    assert report_card.pdf_error_message == ""


@pytest.mark.django_db
def test_report_card_pdf_endpoint_redirects_once_ready_and_409s_before_that(
    api_client, organization, user_factory, report_card_fixture_set, assessment_factory, result_factory,
    django_capture_on_commit_callbacks,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="70.00", status="published")

    user = user_factory(organization=organization, email="admin@example.com", password="s3cret-pass!")
    _grant(user, "report_cards.generate", "report_cards.view")
    _login(api_client, "admin@example.com", "s3cret-pass!")

    with django_capture_on_commit_callbacks(execute=False):
        generated = api_client.post(
            "/api/v1/report-cards/generate",
            {"student": str(fs["student"].public_id), "term": str(fs["term"].public_id)},
            format="json",
        )
    public_id = generated.json()["data"]["public_id"]
    assert generated.json()["data"]["pdf_status"] == "pending"

    not_ready = api_client.get(f"/api/v1/report-cards/{public_id}/pdf")
    assert not_ready.status_code == 409

    from apps.report_cards.models import ReportCard
    from apps.report_cards.tasks.reports import generate_report_card_pdf

    report_card = ReportCard.objects.get(public_id=public_id)
    generate_report_card_pdf(report_card.id, organization.id)
    report_card.refresh_from_db()

    ready = api_client.get(f"/api/v1/report-cards/{public_id}/pdf")
    assert ready.status_code == 302
    assert ready.url
