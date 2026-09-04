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
    assert defaulters[0]["student_public_id"] == str(student.public_id)
    assert defaulters[0]["student_name"] == str(student)
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


@pytest.mark.django_db
def test_dashboard_callback_caches_widgets_for_the_ttl(
    client, superuser, organization, school_factory, student_factory, settings,
):
    _use_plain_staticfiles_storage(settings)
    school = school_factory(organization=organization)
    student_factory(school=school, admission_number="CACHE1")
    client.force_login(superuser)
    activate_organization(None)

    first = client.get(reverse("admin:index"))
    assert first.status_code == 200
    first_kpis = {card["title"]: card["value"] for card in first.context["kpi_cards"]}
    assert first_kpis["Total Students"] == 1

    # A student created after the first request shouldn't show up in the
    # KPI count until the cache entry expires — proves dashboard_callback
    # is actually caching rather than recomputing every request.
    student_factory(school=school, admission_number="CACHE2")
    second = client.get(reverse("admin:index"))
    second_kpis = {card["title"]: card["value"] for card in second.context["kpi_cards"]}
    assert second_kpis["Total Students"] == 1


@pytest.mark.django_db
def test_dashboard_kpi_cards_reflect_real_counts(
    client, superuser, organization, school_factory, student_factory, staff_factory,
    teacher_factory, achievement_factory, settings,
):
    _use_plain_staticfiles_storage(settings)
    school = school_factory(organization=organization)
    student = student_factory(school=school, admission_number="K001")
    staff = staff_factory(school=school, employee_number="EK001")
    teacher_factory(staff=staff)
    achievement_factory(student=student, title="Debate champion")
    client.force_login(superuser)
    activate_organization(None)

    response = client.get(reverse("admin:index"))

    assert response.status_code == 200
    kpis = {card["title"]: card["value"] for card in response.context["kpi_cards"]}
    assert kpis["Total Students"] == 1
    assert kpis["Total Teachers"] == 1
    assert kpis["Total Staff"] == 1
    assert kpis["Achievements"] == 1
    tones = {card["title"]: card["tone"] for card in response.context["kpi_cards"]}
    assert tones["Achievements"] == "blue"
    assert tones["Total Students"] == "amber"


@pytest.mark.django_db
def test_dashboard_gender_breakdown_reflects_real_students(
    client, superuser, organization, school_factory, student_factory, settings,
):
    _use_plain_staticfiles_storage(settings)
    school = school_factory(organization=organization)
    student_factory(school=school, admission_number="G001", gender="male")
    student_factory(school=school, admission_number="G002", gender="male")
    student_factory(school=school, admission_number="G003", gender="female")
    student_factory(school=school, admission_number="G004", gender="")
    client.force_login(superuser)
    activate_organization(None)

    response = client.get(reverse("admin:index"))

    assert response.status_code == 200
    breakdown = response.context["student_gender_breakdown"]
    assert breakdown["male"] == 2
    assert breakdown["female"] == 1
    assert breakdown["unspecified"] == 1
    assert response.context["student_gender_total"] == 4


@pytest.mark.django_db
def test_dashboard_messages_and_unread_count(
    client, superuser, organization, user_factory, message_factory, settings,
):
    _use_plain_staticfiles_storage(settings)
    sender = user_factory(organization=organization, email="sender@example.com")
    message_factory(sender=sender, recipient=superuser, subject="Hello", body="Please review")
    message_factory(sender=sender, recipient=superuser, subject="Read one", is_read=True)
    client.force_login(superuser)
    activate_organization(None)

    response = client.get(reverse("admin:index"))

    assert response.status_code == 200
    messages = response.context["recent_messages"]
    assert len(messages) == 2
    assert response.context["unread_message_count"] == 1


@pytest.mark.django_db
def test_dashboard_notices_from_announcements(
    client, superuser, organization, school_factory, announcement_factory, settings,
):
    _use_plain_staticfiles_storage(settings)
    school = school_factory(organization=organization)
    announcement_factory(school=school, title="Sports day", is_pinned=True)
    client.force_login(superuser)
    activate_organization(None)

    response = client.get(reverse("admin:index"))

    assert response.status_code == 200
    notices = response.context["notices"]
    assert len(notices) == 1
    assert notices[0]["title"] == "Sports day"


@pytest.mark.django_db
def test_dashboard_recent_activity_from_notifications(
    client, superuser, organization, notification_factory, settings,
):
    _use_plain_staticfiles_storage(settings)
    notification_factory(recipient=superuser, title="New payment received")
    client.force_login(superuser)
    activate_organization(None)

    response = client.get(reverse("admin:index"))

    assert response.status_code == 200
    activity = response.context["recent_activity"]
    assert len(activity) == 1
    assert activity[0]["title"] == "New payment received"


@pytest.mark.django_db
def test_dashboard_calendar_includes_real_events_this_month(
    client, superuser, organization, school_factory, student_factory, achievement_factory, settings,
):
    _use_plain_staticfiles_storage(settings)
    school = school_factory(organization=organization)
    student = student_factory(school=school, admission_number="C001")
    today = datetime.date.today()
    achievement_factory(student=student, title="Chess champion", awarded_on=today)
    client.force_login(superuser)
    activate_organization(None)

    response = client.get(reverse("admin:index"))

    assert response.status_code == 200
    calendar = response.context["calendar"]
    assert calendar["year"] == today.year
    assert calendar["month"] == today.month
    matching_day = next(
        day
        for week in calendar["weeks"]
        for day in week
        if day["date"] == today
    )
    assert any("Chess champion" in event for event in matching_day["events"])


@pytest.mark.django_db
def test_achievement_admin_changelist_and_add(
    client, superuser, organization, school_factory, student_factory, settings,
):
    _use_plain_staticfiles_storage(settings)
    school = school_factory(organization=organization)
    student = student_factory(school=school, admission_number="AD001")
    client.force_login(superuser)
    activate_organization(None)

    changelist = client.get(reverse("admin:students_achievement_changelist"))
    assert changelist.status_code == 200

    response = client.post(
        reverse("admin:students_achievement_add"),
        {
            "organization": organization.id,
            "school": school.id,
            "student": student.id,
            "title": "Regional spelling bee winner",
            "category": "academic",
            "description": "",
            "awarded_on": "2026-02-01",
        },
        follow=True,
    )
    assert response.redirect_chain, response.context["errors"] if hasattr(response, "context") and response.context and "errors" in response.context else response.content

    from apps.students.models import Achievement

    assert Achievement.all_tenants.filter(title="Regional spelling bee winner").exists()
