"""A student or guardian account can hold `report_cards.view` (it's what
lets them see their own report cards) but that permission is org-wide by
RBAC design (§8 ARCHITECTURE.md) — nothing in the code stops it, by
itself, from returning every student's report card in the school. These
tests pin the extra scoping in report_card_service.visible_report_cards_for
that a student/guardian account only ever sees its own (or its own
children's) report cards, on list, detail, pdf and audit, regardless of
what student_id/report_card_id/public_id is requested.
"""
import pytest

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.report_cards.services.report_card_service import generate_report_card, publish_report_card


def _grant(user, *codes):
    role = Role.objects.create(name=f"ROLE_{user.pk}_{'_'.join(codes)}"[:100], label="Test Role")
    for code in codes:
        RolePermission.objects.create(role=role, permission=Permission.objects.get(code=code))
    UserRole.objects.create(user=user, role=role)


def _login(api_client, email, password):
    resp = api_client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    token = resp.json()["data"]["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


@pytest.fixture
def two_students_with_report_cards(
    organization, report_card_fixture_set, student_factory, enrollment_factory,
    assessment_factory, result_factory,
):
    """Own = report_card_fixture_set's student; other = a second student in
    the same school/class/term with their own published report card."""
    fs = report_card_fixture_set
    other_student = student_factory(school=fs["school"], admission_number="A002", first_name="Other")
    enrollment_factory(student=other_student, class_arm=fs["class_arm"], academic_year=fs["academic_year"])

    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="70.00", status="published")
    result_factory(assessment=assessment, student=other_student, score="55.00", status="published")

    own_card = publish_report_card(
        report_card=generate_report_card(student=fs["student"], term=fs["term"], actor=None), actor=None
    )
    other_card = publish_report_card(
        report_card=generate_report_card(student=other_student, term=fs["term"], actor=None), actor=None
    )
    return {**fs, "other_student": other_student, "own_card": own_card, "other_card": other_card}


@pytest.mark.django_db
def test_student_list_view_only_returns_own_report_cards(
    api_client, organization, user_factory, two_students_with_report_cards,
):
    fs = two_students_with_report_cards
    student_user = user_factory(organization=organization, email="student@example.com", password="s3cret-pass!")
    fs["student"].user = student_user
    fs["student"].save(update_fields=["user"])
    _grant(student_user, "report_cards.view")
    _login(api_client, "student@example.com", "s3cret-pass!")

    unfiltered = api_client.get("/api/v1/report-cards")
    assert unfiltered.status_code == 200
    ids = {row["public_id"] for row in unfiltered.json()["data"]["results"]}
    assert ids == {str(fs["own_card"].public_id)}

    spoofed = api_client.get(f"/api/v1/report-cards?student_id={fs['other_student'].public_id}")
    assert spoofed.status_code == 200
    assert spoofed.json()["data"]["results"] == []


@pytest.mark.django_db
def test_student_cannot_fetch_another_students_report_card_detail_or_pdf(
    api_client, organization, user_factory, two_students_with_report_cards,
):
    fs = two_students_with_report_cards
    student_user = user_factory(organization=organization, email="student@example.com", password="s3cret-pass!")
    fs["student"].user = student_user
    fs["student"].save(update_fields=["user"])
    _grant(student_user, "report_cards.view")
    _login(api_client, "student@example.com", "s3cret-pass!")

    own_detail = api_client.get(f"/api/v1/report-cards/{fs['own_card'].public_id}")
    assert own_detail.status_code == 200

    other_detail = api_client.get(f"/api/v1/report-cards/{fs['other_card'].public_id}")
    assert other_detail.status_code == 404

    other_pdf = api_client.get(f"/api/v1/report-cards/{fs['other_card'].public_id}/pdf")
    assert other_pdf.status_code == 404


@pytest.mark.django_db
def test_guardian_only_sees_own_childrens_report_cards(
    api_client, organization, user_factory, guardian_factory, guardian_student_factory,
    two_students_with_report_cards,
):
    fs = two_students_with_report_cards
    guardian_user = user_factory(organization=organization, email="guardian@example.com", password="s3cret-pass!")
    guardian = guardian_factory(organization=organization, user=guardian_user)
    guardian_student_factory(student=fs["student"], guardian=guardian)
    _grant(guardian_user, "report_cards.view")
    _login(api_client, "guardian@example.com", "s3cret-pass!")

    listed = api_client.get("/api/v1/report-cards")
    assert listed.status_code == 200
    ids = {row["public_id"] for row in listed.json()["data"]["results"]}
    assert ids == {str(fs["own_card"].public_id)}

    other_detail = api_client.get(f"/api/v1/report-cards/{fs['other_card'].public_id}")
    assert other_detail.status_code == 404


@pytest.mark.django_db
def test_staff_role_is_not_scoped_and_sees_every_students_report_card(
    api_client, organization, user_factory, two_students_with_report_cards,
):
    """A user with no student_profile/guardian_profile (an ordinary staff
    account) is unaffected by the new scoping — report_cards.view stays
    the org-wide management permission it always was."""
    fs = two_students_with_report_cards
    staff_user = user_factory(organization=organization, email="staff@example.com", password="s3cret-pass!")
    _grant(staff_user, "report_cards.view")
    _login(api_client, "staff@example.com", "s3cret-pass!")

    listed = api_client.get("/api/v1/report-cards")
    assert listed.status_code == 200
    ids = {row["public_id"] for row in listed.json()["data"]["results"]}
    assert ids == {str(fs["own_card"].public_id), str(fs["other_card"].public_id)}
