import pytest
from django.db import ProgrammingError, connection, transaction

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.report_cards.models import ReportCardAudit
from apps.report_cards.services.report_card_service import (
    archive_report_card,
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
def test_generate_report_card_writes_a_generated_audit_row(
    organization, report_card_fixture_set, assessment_factory, result_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="70.00", status="published")

    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)

    entries = list(ReportCardAudit.objects.filter(report_card=report_card))
    assert len(entries) == 1
    assert entries[0].action == "generated"
    assert entries[0].previous_status == ""
    assert entries[0].new_status == "generated"


@pytest.mark.django_db
def test_regenerating_writes_a_regenerated_audit_row(
    organization, report_card_fixture_set, assessment_factory, result_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="70.00", status="published")
    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)
    publish_report_card(report_card=report_card, actor=None)

    generate_report_card(student=fs["student"], term=fs["term"], actor=None)

    entries = list(ReportCardAudit.objects.filter(report_card=report_card).order_by("created_at"))
    assert [e.action for e in entries] == ["generated", "published", "regenerated"]
    regenerated = entries[-1]
    assert regenerated.previous_status == "published"
    assert regenerated.new_status == "generated"


@pytest.mark.django_db
def test_publish_unpublish_archive_write_audit_rows(
    organization, report_card_fixture_set, assessment_factory, result_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="70.00", status="published")
    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)

    publish_report_card(report_card=report_card, actor=None)
    unpublish_report_card(report_card=report_card, actor=None)
    archive_report_card(report_card=report_card, actor=None)

    actions = list(
        ReportCardAudit.objects.filter(report_card=report_card).order_by("created_at").values_list(
            "action", "previous_status", "new_status"
        )
    )
    assert actions == [
        ("generated", "", "generated"),
        ("published", "generated", "published"),
        ("unpublished", "published", "generated"),
        ("archived", "generated", "archived"),
    ]


@pytest.mark.django_db
def test_report_card_audit_endpoint_lists_and_filters(
    api_client, organization, user_factory, report_card_fixture_set, assessment_factory, result_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="70.00", status="published")
    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)
    publish_report_card(report_card=report_card, actor=None)

    user = user_factory(organization=organization, email="admin@example.com", password="s3cret-pass!")
    _grant(user, "report_cards.view")
    _login(api_client, "admin@example.com", "s3cret-pass!")

    resp = api_client.get("/api/v1/report-cards/audit")
    assert resp.status_code == 200
    rows = resp.json()["data"]["results"]
    assert len(rows) == 2
    assert {row["action"] for row in rows} == {"generated", "published"}

    filtered = api_client.get(f"/api/v1/report-cards/audit?report_card_id={report_card.public_id}")
    assert filtered.status_code == 200
    assert len(filtered.json()["data"]["results"]) == 2


@pytest.mark.django_db
def test_report_card_audit_endpoint_requires_permission(
    api_client, organization, user_factory,
):
    user_factory(organization=organization, email="noperm@example.com", password="s3cret-pass!")
    _login(api_client, "noperm@example.com", "s3cret-pass!")

    resp = api_client.get("/api/v1/report-cards/audit")
    assert resp.status_code == 403


@pytest.mark.skipif(connection.vendor != "postgresql", reason="append-only trigger is Postgres-only")
@pytest.mark.django_db
def test_report_card_audit_is_append_only_at_db_level(
    organization, report_card_fixture_set, assessment_factory, result_factory,
):
    fs = report_card_fixture_set
    assessment = assessment_factory(class_subject=fs["class_subject"], term=fs["term"], score_category="ca")
    result_factory(assessment=assessment, student=fs["student"], score="70.00", status="published")
    report_card = generate_report_card(student=fs["student"], term=fs["term"], actor=None)

    activate_organization(organization.id)
    audit = ReportCardAudit.objects.filter(report_card=report_card).first()

    with pytest.raises(ProgrammingError, match="append-only"):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE report_cards_report_card_audit SET new_status = %s WHERE id = %s",
                    ["published", audit.id],
                )

    with pytest.raises(ProgrammingError, match="append-only"):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM report_cards_report_card_audit WHERE id = %s", [audit.id])
