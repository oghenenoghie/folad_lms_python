from decimal import Decimal

import pytest

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.report_cards.models import PsychomotorTrait
from apps.report_cards.services.report_card_service import (
    DEFAULT_PSYCHOMOTOR_TRAITS,
    InvalidPsychomotorRating,
    generate_report_card,
    get_or_create_default_traits,
    set_psychomotor_ratings,
)


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
def test_get_or_create_default_traits_seeds_the_standard_checklist(organization, report_card_fixture_set):
    school = report_card_fixture_set["school"]

    traits = get_or_create_default_traits(school=school)

    assert [t.name for t in traits] == DEFAULT_PSYCHOMOTOR_TRAITS
    assert PsychomotorTrait.objects.filter(school=school).count() == len(DEFAULT_PSYCHOMOTOR_TRAITS)


@pytest.mark.django_db
def test_get_or_create_default_traits_is_idempotent_and_respects_customization(
    organization, report_card_fixture_set,
):
    school = report_card_fixture_set["school"]
    get_or_create_default_traits(school=school)
    PsychomotorTrait.objects.filter(school=school, name="Sports/Games").delete()
    PsychomotorTrait.objects.create(organization=organization, school=school, name="Custom Trait", order=99)

    traits = get_or_create_default_traits(school=school)

    # A school with any traits already configured is left exactly as-is —
    # the defaults are a first-use seed, not something re-applied on top.
    names = {t.name for t in traits}
    assert "Custom Trait" in names
    assert "Sports/Games" not in names


@pytest.mark.django_db
def test_generate_report_card_seeds_default_traits_for_the_school(
    organization, report_card_fixture_set, assessment_factory, result_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="70.00", status="published")

    generate_report_card(student=fs["student"], term=fs["term"], actor=None)

    assert PsychomotorTrait.objects.filter(school=fs["school"]).count() == len(DEFAULT_PSYCHOMOTOR_TRAITS)


@pytest.mark.django_db
def test_generate_report_card_sets_overall_grade_and_remark(
    organization, report_card_fixture_set, assessment_factory, result_factory,
    grading_scheme_factory, grade_band_factory,
):
    fs = report_card_fixture_set
    scheme = grading_scheme_factory(school=fs["school"])
    grade_band_factory(grading_scheme=scheme, grade="A", min_score="70.00", max_score="100.00", remark="Excellent")
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="80.00", status="published")

    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)

    assert report_card.overall_grade == "A"
    assert report_card.overall_remark == "Excellent"


@pytest.mark.django_db
def test_recompute_positions_sets_class_average_on_every_subject_row(
    organization, report_card_fixture_set, student_factory, enrollment_factory,
    assessment_factory, result_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="60.00", status="published")

    other_student = student_factory(school=fs["school"], admission_number="A002")
    enrollment_factory(student=other_student, class_arm=fs["class_arm"], academic_year=fs["academic_year"])
    result_factory(assessment=assessment, student=other_student, score="80.00", status="published")

    low_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)
    generate_report_card(student=other_student, term=fs["term"], actor=None)
    low_card.refresh_from_db()

    subject_row = low_card.subjects.get(subject=fs["subject"])
    assert subject_row.class_average == Decimal("70.00")


@pytest.mark.django_db
def test_set_psychomotor_ratings_upserts_and_rejects_a_trait_from_another_school(
    organization, report_card_fixture_set, school_factory, report_card_factory,
):
    fs = report_card_fixture_set
    report_card = report_card_factory(student=fs["student"], term=fs["term"], class_arm=fs["class_arm"])
    traits = get_or_create_default_traits(school=fs["school"])
    punctuality = traits[0]

    saved = set_psychomotor_ratings(report_card=report_card, ratings={punctuality.id: 5}, actor=None)
    assert saved[0].rating == 5

    # Upsert: submitting the same trait again updates rather than duplicating.
    set_psychomotor_ratings(report_card=report_card, ratings={punctuality.id: 3}, actor=None)
    assert report_card.psychomotor_ratings.get(trait=punctuality).rating == 3
    assert report_card.psychomotor_ratings.count() == 1

    other_school = school_factory(organization=organization, name="Other School", code="OTH")
    foreign_trait = get_or_create_default_traits(school=other_school)[0]
    with pytest.raises(InvalidPsychomotorRating):
        set_psychomotor_ratings(report_card=report_card, ratings={foreign_trait.id: 4}, actor=None)


@pytest.mark.django_db
def test_psychomotor_trait_api_crud_and_permissions(
    api_client, organization, user_factory, report_card_fixture_set,
):
    fs = report_card_fixture_set
    user = user_factory(organization=organization, email="admin@example.com", password="s3cret-pass!")
    _grant(user, "psychomotor_traits.view", "psychomotor_traits.create", "psychomotor_traits.update")
    _login(api_client, "admin@example.com", "s3cret-pass!")

    created = api_client.post(
        "/api/v1/psychomotor-traits",
        {"school": str(fs["school"].public_id), "name": "Creativity", "order": 1},
        format="json",
    )
    assert created.status_code == 201
    public_id = created.json()["data"]["public_id"]

    listed = api_client.get(f"/api/v1/psychomotor-traits?school_id={fs['school'].public_id}")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1

    updated = api_client.patch(f"/api/v1/psychomotor-traits/{public_id}", {"order": 2}, format="json")
    assert updated.status_code == 200
    assert updated.json()["data"]["order"] == 2


@pytest.mark.django_db
def test_psychomotor_trait_api_requires_permission(api_client, organization, user_factory, report_card_fixture_set):
    fs = report_card_fixture_set
    user_factory(organization=organization, email="norole@example.com", password="s3cret-pass!")
    _login(api_client, "norole@example.com", "s3cret-pass!")

    denied = api_client.post(
        "/api/v1/psychomotor-traits",
        {"school": str(fs["school"].public_id), "name": "Creativity"},
        format="json",
    )
    assert denied.status_code == 403


@pytest.mark.django_db
def test_patch_report_card_sets_psychomotor_ratings(
    api_client, organization, user_factory, report_card_fixture_set, assessment_factory, result_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="75.00", status="published")

    user = user_factory(organization=organization, email="admin@example.com", password="s3cret-pass!")
    _grant(user, "report_cards.generate", "report_cards.view", "report_cards.update")
    _login(api_client, "admin@example.com", "s3cret-pass!")

    generated = api_client.post(
        "/api/v1/report-cards/generate",
        {"student": str(fs["student"].public_id), "term": str(fs["term"].public_id)},
        format="json",
    )
    public_id = generated.json()["data"]["public_id"]
    trait = PsychomotorTrait.objects.filter(school=fs["school"]).order_by("order").first()

    rated = api_client.patch(
        f"/api/v1/report-cards/{public_id}",
        {"psychomotor_ratings": [{"trait": str(trait.public_id), "rating": 5}]},
        format="json",
    )

    assert rated.status_code == 200
    ratings = rated.json()["data"]["psychomotor_ratings"]
    assert len(ratings) == 1
    assert ratings[0]["rating"] == 5
    assert ratings[0]["rating_label"] == "Excellent"
    assert ratings[0]["trait_name"] == trait.name


@pytest.mark.django_db
def test_patch_report_card_rejects_a_trait_from_a_different_school(
    api_client, organization, user_factory, report_card_fixture_set, school_factory,
    assessment_factory, result_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="75.00", status="published")

    user = user_factory(organization=organization, email="admin@example.com", password="s3cret-pass!")
    _grant(user, "report_cards.generate", "report_cards.view", "report_cards.update")
    _login(api_client, "admin@example.com", "s3cret-pass!")

    generated = api_client.post(
        "/api/v1/report-cards/generate",
        {"student": str(fs["student"].public_id), "term": str(fs["term"].public_id)},
        format="json",
    )
    public_id = generated.json()["data"]["public_id"]
    other_school = school_factory(organization=organization, name="Other School", code="OTH")
    foreign_trait = get_or_create_default_traits(school=other_school)[0]

    rated = api_client.patch(
        f"/api/v1/report-cards/{public_id}",
        {"psychomotor_ratings": [{"trait": str(foreign_trait.public_id), "rating": 5}]},
        format="json",
    )

    assert rated.status_code == 400


@pytest.mark.django_db
def test_render_report_card_pdf_includes_psychomotor_and_grading_legend_when_present(
    organization, report_card_fixture_set, assessment_factory, result_factory,
    grading_scheme_factory, grade_band_factory,
):
    from apps.report_cards.services.report_card_pdf_service import render_report_card_pdf

    fs = report_card_fixture_set
    scheme = grading_scheme_factory(school=fs["school"])
    grade_band_factory(grading_scheme=scheme, grade="A", min_score="70.00", max_score="100.00")
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="80.00", status="published")

    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)
    trait = PsychomotorTrait.objects.filter(school=fs["school"]).order_by("order").first()
    set_psychomotor_ratings(report_card=report_card, ratings={trait.id: 4}, actor=None)
    report_card.refresh_from_db()

    pdf_bytes = render_report_card_pdf(report_card)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


@pytest.mark.django_db
def test_render_report_card_pdf_skips_psychomotor_section_when_unrated(
    organization, report_card_fixture_set, assessment_factory, result_factory,
):
    from apps.report_cards.services.report_card_pdf_service import _psychomotor_table

    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="80.00", status="published")

    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)

    assert _psychomotor_table(report_card) is None


@pytest.mark.django_db
def test_report_card_verify_endpoint_includes_overall_grade_and_psychomotor_ratings(
    api_client, organization, report_card_fixture_set, assessment_factory, result_factory,
    grading_scheme_factory, grade_band_factory,
):
    from apps.report_cards.services.report_card_service import publish_report_card

    fs = report_card_fixture_set
    scheme = grading_scheme_factory(school=fs["school"])
    grade_band_factory(grading_scheme=scheme, grade="A", min_score="70.00", max_score="100.00", remark="Excellent")
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="88.00", status="published")

    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)
    trait = PsychomotorTrait.objects.filter(school=fs["school"]).order_by("order").first()
    set_psychomotor_ratings(report_card=report_card, ratings={trait.id: 5}, actor=None)
    publish_report_card(report_card=report_card, actor=None)

    resp = api_client.get(f"/api/v1/report-cards/verify/{report_card.verification_code}")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["overall_grade"] == "A"
    assert data["overall_remark"] == "Excellent"
    # Only one student in this class arm this term, so the "class average"
    # is just their own percentage.
    assert data["subjects"][0]["class_average"] == "88.00"
    assert len(data["psychomotor_ratings"]) == 1
    assert data["psychomotor_ratings"][0]["rating"] == 5
    assert data["psychomotor_ratings"][0]["trait_name"] == trait.name
