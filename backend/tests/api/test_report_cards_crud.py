from decimal import Decimal

import pytest

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.report_cards.models import ReportCard
from apps.report_cards.services.report_card_service import (
    InvalidReportCardTransition,
    ReportCardError,
    generate_report_card,
    publish_report_card,
    unpublish_report_card,
)
from apps.tenancy.context import activate_organization


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
def test_generate_report_card_consolidates_ca_cbt_exam_by_configured_weight(
    organization, report_card_fixture_set, assessment_factory, result_factory,
    report_card_weighting_factory, grading_scheme_factory, grade_band_factory,
):
    fs = report_card_fixture_set
    report_card_weighting_factory(school=fs["school"], ca_weight="20.00", cbt_weight="30.00", exam_weight="50.00")
    scheme = grading_scheme_factory(school=fs["school"])
    grade_band_factory(grading_scheme=scheme, grade="A", min_score="70.00", max_score="100.00")

    ca = assessment_factory(
        class_subject=fs["class_subject"], term=fs["term"], name="CA", score_category="ca", max_score="20.00"
    )
    cbt = assessment_factory(
        class_subject=fs["class_subject"], term=fs["term"], name="CBT", score_category="cbt", max_score="30.00"
    )
    exam = assessment_factory(
        class_subject=fs["class_subject"], term=fs["term"], name="Exam", score_category="exam", max_score="50.00"
    )
    result_factory(assessment=ca, student=fs["student"], score="18.00", status="published")
    result_factory(assessment=cbt, student=fs["student"], score="26.00", status="published")
    result_factory(assessment=exam, student=fs["student"], score="42.00", status="published")

    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)

    subject_row = report_card.subjects.get(subject=fs["subject"])
    assert subject_row.ca_score == Decimal("18.00")
    assert subject_row.cbt_score == Decimal("26.00")
    assert subject_row.exam_score == Decimal("42.00")
    assert subject_row.total_score == Decimal("86.00")
    assert subject_row.percentage == Decimal("86.00")
    assert subject_row.grade == "A"
    assert report_card.average_percentage == Decimal("86.00")
    assert report_card.status == "generated"
    assert report_card.report_card_number.startswith("RC-")
    assert report_card.verification_code


@pytest.mark.django_db
def test_generate_report_card_renormalizes_when_a_category_is_missing(
    organization, report_card_fixture_set, assessment_factory, result_factory,
    report_card_weighting_factory,
):
    """A subject with no CBT assessment this term isn't penalized for a
    category that was never administered — its total is rescaled over
    just the categories that exist (here CA 20 + Exam 50 = 70)."""
    fs = report_card_fixture_set
    report_card_weighting_factory(school=fs["school"], ca_weight="20.00", cbt_weight="30.00", exam_weight="50.00")

    ca = assessment_factory(
        class_subject=fs["class_subject"], term=fs["term"], name="CA", score_category="ca", max_score="20.00"
    )
    exam = assessment_factory(
        class_subject=fs["class_subject"], term=fs["term"], name="Exam", score_category="exam", max_score="50.00"
    )
    result_factory(assessment=ca, student=fs["student"], score="14.00", status="published")
    result_factory(assessment=exam, student=fs["student"], score="35.00", status="published")

    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)
    subject_row = report_card.subjects.get(subject=fs["subject"])

    assert subject_row.cbt_score == Decimal("0.00")
    assert subject_row.cbt_max_score == Decimal("0.00")
    # (14 + 35) / (20 + 50) * 100 = 70.00
    assert subject_row.percentage == Decimal("70.00")


@pytest.mark.django_db
def test_generate_report_card_only_counts_published_results(
    organization, report_card_fixture_set, assessment_factory, result_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="90.00", status="entered")

    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)

    assert report_card.subjects.count() == 0
    assert report_card.average_percentage == Decimal("0.00")


@pytest.mark.django_db
def test_generate_report_card_computes_attendance_summary(
    organization, report_card_fixture_set, attendance_factory,
):
    fs = report_card_fixture_set
    enrollment = fs["enrollment"]
    for date, status in [
        ("2025-09-02", "present"), ("2025-09-03", "present"), ("2025-09-04", "absent"),
    ]:
        attendance_factory(enrollment=enrollment, date=date, status=status)

    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)

    assert report_card.attendance_present == 2
    assert report_card.attendance_absent == 1
    assert report_card.attendance_percentage == Decimal("66.67")


@pytest.mark.django_db
def test_generate_report_card_requires_enrollment(organization, report_card_fixture_set, student_factory):
    fs = report_card_fixture_set
    unenrolled = student_factory(school=fs["school"], admission_number="A002")

    with pytest.raises(ReportCardError):
        generate_report_card(student=unenrolled, term=fs["term"], actor=None)


@pytest.mark.django_db
def test_class_position_ranks_students_within_the_same_class_arm(
    organization, report_card_fixture_set, student_factory, enrollment_factory,
    assessment_factory, result_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="60.00", status="published")

    top_student = student_factory(school=fs["school"], admission_number="A002")
    enrollment_factory(student=top_student, class_arm=fs["class_arm"], academic_year=fs["academic_year"])
    result_factory(assessment=assessment, student=top_student, score="95.00", status="published")

    low_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)
    top_card = generate_report_card(student=top_student, term=fs["term"], actor=None)
    low_card.refresh_from_db()

    assert top_card.class_position == 1
    assert low_card.class_position == 2
    assert top_card.class_size == 2
    assert low_card.class_size == 2


@pytest.mark.django_db
def test_publish_requires_generated_status_and_unpublish_reverts_it(
    organization, report_card_fixture_set,
):
    fs = report_card_fixture_set
    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)
    assert report_card.status == "generated"

    with pytest.raises(InvalidReportCardTransition):
        unpublish_report_card(report_card=report_card, actor=None)

    published = publish_report_card(report_card=report_card, actor=None)
    assert published.status == "published"
    assert published.published_at is not None

    with pytest.raises(InvalidReportCardTransition):
        publish_report_card(report_card=published, actor=None)

    unpublished = unpublish_report_card(report_card=published, actor=None)
    assert unpublished.status == "generated"
    assert unpublished.published_at is None


@pytest.mark.django_db
def test_regenerate_reverts_a_published_report_card_to_generated(
    organization, report_card_fixture_set, assessment_factory, result_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="60.00", status="published")

    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)
    original_number = report_card.report_card_number
    publish_report_card(report_card=report_card, actor=None)

    regenerated = generate_report_card(student=fs["student"], term=fs["term"], actor=None)

    assert regenerated.id == report_card.id
    assert regenerated.report_card_number == original_number
    assert regenerated.status == "generated"
    assert regenerated.published_at is None


@pytest.mark.django_db
def test_report_card_api_generate_view_and_publish_workflow(
    api_client, organization, user_factory, report_card_fixture_set, assessment_factory, result_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="75.00", status="published")

    user = user_factory(organization=organization, email="admin@example.com", password="s3cret-pass!")
    _grant(user, "report_cards.generate", "report_cards.view", "report_cards.publish", "report_cards.update")
    _login(api_client, "admin@example.com", "s3cret-pass!")

    generated = api_client.post(
        "/api/v1/report-cards/generate",
        {"student": str(fs["student"].public_id), "term": str(fs["term"].public_id)},
        format="json",
    )
    assert generated.status_code == 200
    body = generated.json()["data"]
    assert body["status"] == "generated"
    public_id = body["public_id"]
    assert len(body["subjects"]) == 1

    listed = api_client.get(f"/api/v1/report-cards?student_id={fs['student'].public_id}")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1

    commented = api_client.patch(
        f"/api/v1/report-cards/{public_id}", {"teacher_comment": "Great effort this term."}, format="json"
    )
    assert commented.status_code == 200
    assert commented.json()["data"]["teacher_comment"] == "Great effort this term."
    # Calculated fields aren't client-writable even if sent.
    assert commented.json()["data"]["status"] == "generated"

    published = api_client.post(f"/api/v1/report-cards/{public_id}/publish")
    assert published.status_code == 200
    assert published.json()["data"]["status"] == "published"

    republish_attempt = api_client.post(f"/api/v1/report-cards/{public_id}/publish")
    assert republish_attempt.status_code == 409

    unpublished = api_client.post(f"/api/v1/report-cards/{public_id}/unpublish")
    assert unpublished.status_code == 200
    assert unpublished.json()["data"]["status"] == "generated"


@pytest.mark.django_db
def test_report_card_api_requires_permission(api_client, organization, user_factory, report_card_fixture_set):
    fs = report_card_fixture_set
    user_factory(organization=organization, email="norole@example.com", password="s3cret-pass!")
    _login(api_client, "norole@example.com", "s3cret-pass!")

    denied = api_client.post(
        "/api/v1/report-cards/generate",
        {"student": str(fs["student"].public_id), "term": str(fs["term"].public_id)},
        format="json",
    )
    assert denied.status_code == 403


@pytest.mark.django_db
def test_report_cards_app_layer_tenant_isolation(
    organization, other_organization, report_card_fixture_set, assessment_factory, result_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="80.00", status="published")
    generate_report_card(student=fs["student"], term=fs["term"], actor=None)

    activate_organization(other_organization.id)
    try:
        assert ReportCard.objects.count() == 0
    finally:
        activate_organization(organization.id)

    assert ReportCard.objects.count() == 1
