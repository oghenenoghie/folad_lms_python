"""apps.core.dashboard.dashboard_callback runs only inside Django Admin's
own request cycle (it relies on all_tenants + AdminPlatformModeMiddleware's
RLS bypass for cross-tenant visibility, same as every other admin-only
query in this codebase) — so these go through the real admin index view
via the test client rather than calling the callback function directly."""
import datetime

import pytest
from django.urls import reverse

from apps.tenancy.context import activate_organization


@pytest.fixture
def superuser(user_factory, organization):
    return user_factory(
        organization=organization, email="admin@example.com", password="s3cret-pass!",
        is_staff=True, is_superuser=True,
    )


def _use_plain_staticfiles_storage(settings):
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


@pytest.mark.django_db
def test_dashboard_stat_cards_reflect_real_counts(
    client, superuser, organization, school_factory, student_factory, staff_factory, settings,
):
    _use_plain_staticfiles_storage(settings)
    school = school_factory(organization=organization)
    student_factory(school=school, admission_number="A100")
    student_factory(school=school, admission_number="A101", enrollment_status="withdrawn")
    staff_factory(school=school, employee_number="E100")
    client.force_login(superuser)
    activate_organization(None)

    response = client.get(reverse("admin:index"))

    assert response.status_code == 200
    cards = {card["title"]: card["value"] for card in response.context["stat_cards"]}
    assert cards["Active students"] == 1
    assert cards["Active staff"] == 1
    assert cards["New admissions (this month)"] == 2


@pytest.mark.django_db
def test_dashboard_today_collection_and_receivables(
    client, superuser, organization, school_factory, student_factory, term_factory,
    academic_year_factory, invoice_factory, payment_factory, settings,
):
    _use_plain_staticfiles_storage(settings)
    school = school_factory(organization=organization)
    term = term_factory(academic_year=academic_year_factory(school=school))
    student = student_factory(school=school)

    paid_today = invoice_factory(
        student=student, term=term, invoice_number="INV-TODAY", total_minor=100_000, status="issued"
    )
    payment_factory(invoice=paid_today, reference="PAY-TODAY", amount_minor=100_000)

    overdue = invoice_factory(
        student=student, term=term, invoice_number="INV-OVERDUE", total_minor=50_000,
        status="issued", due_date=datetime.date.today() - datetime.timedelta(days=10),
    )
    client.force_login(superuser)
    activate_organization(None)

    response = client.get(reverse("admin:index"))

    assert response.status_code == 200
    cards = {card["title"]: card["value"] for card in response.context["stat_cards"]}
    assert cards["Today's collection"] == "1,000.00"
    assert response.context["total_receivables_subtitle"] == "Total receivables: 500.00"

    defaulters = response.context["top_defaulters"]
    assert len(defaulters) == 1
    assert defaulters[0]["student"] == student
    assert defaulters[0]["outstanding_minor"] == overdue.total_minor
    assert defaulters[0]["days_overdue"] == 10


@pytest.mark.django_db
def test_dashboard_top_defaulters_excludes_fully_paid_invoices(
    client, superuser, organization, school_factory, student_factory, term_factory,
    academic_year_factory, invoice_factory, payment_factory, settings,
):
    _use_plain_staticfiles_storage(settings)
    school = school_factory(organization=organization)
    term = term_factory(academic_year=academic_year_factory(school=school))
    student = student_factory(school=school)

    fully_paid_overdue = invoice_factory(
        student=student, term=term, invoice_number="INV-PAID", total_minor=100_000,
        status="issued", due_date=datetime.date.today() - datetime.timedelta(days=5),
    )
    payment_factory(invoice=fully_paid_overdue, reference="PAY-FULL", amount_minor=100_000)
    client.force_login(superuser)
    activate_organization(None)

    response = client.get(reverse("admin:index"))

    assert response.status_code == 200
    assert response.context["top_defaulters"] == []


@pytest.mark.django_db
def test_dashboard_attendance_today_and_heatmap(
    client, superuser, organization, school_factory, campus_factory, class_level_factory,
    class_arm_factory, academic_year_factory, student_factory, enrollment_factory,
    attendance_factory, settings,
):
    _use_plain_staticfiles_storage(settings)
    school = school_factory(organization=organization)
    class_arm = class_arm_factory(class_level=class_level_factory(campus=campus_factory(school=school)))
    academic_year = academic_year_factory(school=school)
    today = datetime.date.today()

    present_student = student_factory(school=school, admission_number="A200")
    absent_student = student_factory(school=school, admission_number="A201")
    present_enrollment = enrollment_factory(
        student=present_student, class_arm=class_arm, academic_year=academic_year
    )
    absent_enrollment = enrollment_factory(
        student=absent_student, class_arm=class_arm, academic_year=academic_year
    )
    attendance_factory(enrollment=present_enrollment, date=today, status="present")
    attendance_factory(enrollment=absent_enrollment, date=today, status="absent")

    client.force_login(superuser)
    activate_organization(None)

    response = client.get(reverse("admin:index"))

    assert response.status_code == 200
    cards = {card["title"]: card["value"] for card in response.context["stat_cards"]}
    assert cards["Attendance today"] == "50.0%"

    heatmap = response.context["attendance_heatmap"]
    class_level_name = class_arm.class_level.name
    row = next(r for r in heatmap["classes"] if r["name"] == class_level_name)
    assert row["values"][-1] == 50


@pytest.mark.django_db
def test_dashboard_attendance_today_with_no_records_shows_dash(
    client, superuser, organization, settings,
):
    _use_plain_staticfiles_storage(settings)
    client.force_login(superuser)
    activate_organization(None)

    response = client.get(reverse("admin:index"))

    assert response.status_code == 200
    cards = {card["title"]: card["value"] for card in response.context["stat_cards"]}
    assert cards["Attendance today"] == "—"
