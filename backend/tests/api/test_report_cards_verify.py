import pytest

from reportlab.graphics.shapes import Drawing
from reportlab.platypus import Table

from apps.report_cards.services.report_card_pdf_service import (
    _verification_footer,
    _verification_url,
    render_report_card_pdf,
)
from apps.report_cards.services.report_card_service import (
    generate_report_card,
    publish_report_card,
    verify_report_card,
)


@pytest.mark.django_db
def test_verify_report_card_returns_none_before_publish(
    organization, report_card_fixture_set, assessment_factory, result_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="65.00", status="published")
    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)

    assert verify_report_card(verification_code=report_card.verification_code) is None


@pytest.mark.django_db
def test_verify_report_card_returns_published_report_card(
    organization, report_card_fixture_set, assessment_factory, result_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="90.00", status="published")
    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)
    publish_report_card(report_card=report_card, actor=None)

    verified = verify_report_card(verification_code=report_card.verification_code)

    assert verified is not None
    assert verified.id == report_card.id


@pytest.mark.django_db
def test_verify_report_card_returns_archived_report_card(
    organization, report_card_fixture_set, assessment_factory, result_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="55.00", status="published")
    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)
    publish_report_card(report_card=report_card, actor=None)
    report_card.status = "archived"
    report_card.save(update_fields=["status"])

    assert verify_report_card(verification_code=report_card.verification_code) is not None


@pytest.mark.django_db
def test_verify_report_card_returns_none_for_unknown_code(organization):
    assert verify_report_card(verification_code="does-not-exist") is None


@pytest.mark.django_db
def test_report_card_verify_endpoint_returns_public_payload_without_auth(
    api_client, organization, report_card_fixture_set, assessment_factory, result_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="88.00", status="published")
    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)
    publish_report_card(report_card=report_card, actor=None)

    resp = api_client.get(f"/api/v1/report-cards/verify/{report_card.verification_code}")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["report_card_number"] == report_card.report_card_number
    assert data["student_name"] == f"{fs['student'].first_name} {fs['student'].last_name}"
    assert data["school_name"] == fs["school"].name
    assert data["status"] == "published"
    assert len(data["subjects"]) == 1
    assert data["subjects"][0]["subject"] == fs["subject"].name
    assert "teacher_comment" not in data
    assert "principal_comment" not in data


@pytest.mark.django_db
def test_report_card_verify_endpoint_404s_for_unknown_code(api_client, organization):
    resp = api_client.get("/api/v1/report-cards/verify/not-a-real-code")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_report_card_verify_endpoint_404s_for_unpublished_report_card(
    api_client, organization, report_card_fixture_set, assessment_factory, result_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="70.00", status="published")
    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)

    resp = api_client.get(f"/api/v1/report-cards/verify/{report_card.verification_code}")

    assert resp.status_code == 404


@pytest.mark.django_db
def test_verification_url_points_at_configured_frontend(
    settings, organization, report_card_fixture_set, assessment_factory, result_factory,
):
    settings.FRONTEND_URL = "https://portal.example.com/"
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="60.00", status="published")
    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)

    url = _verification_url(report_card)

    assert url == f"https://portal.example.com/report/verify/{report_card.verification_code}"


@pytest.mark.django_db
def test_verification_footer_embeds_a_qr_drawing_next_to_the_codes(
    organization, report_card_fixture_set, assessment_factory, result_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="72.00", status="published")
    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)

    footer = _verification_footer(report_card)

    assert isinstance(footer, Table)
    qr_cell = footer._cellvalues[0][0]
    assert isinstance(qr_cell, Drawing)


@pytest.mark.django_db
def test_render_report_card_pdf_still_renders_with_the_verification_footer(
    organization, report_card_fixture_set, assessment_factory, result_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="72.00", status="published")
    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)

    pdf_bytes = render_report_card_pdf(report_card)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500
