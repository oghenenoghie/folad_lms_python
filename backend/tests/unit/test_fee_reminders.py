import datetime
import io

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.communication.models import Notification
from apps.finance.services import reminder_service
from apps.finance.tasks.notifications import send_fee_reminders
from apps.tenancy.context import activate_organization


@pytest.mark.django_db
def test_reminds_an_invoice_due_soon_and_notifies_student_and_guardian(
    organization, user_factory, school_factory, term_factory, academic_year_factory,
    student_factory, guardian_factory, guardian_student_factory, invoice_factory,
):
    school = school_factory(organization=organization)
    term = term_factory(academic_year=academic_year_factory(school=school))
    student_user = user_factory(organization=organization, email="student@example.com")
    student = student_factory(school=school, user=student_user)
    guardian_user = user_factory(organization=organization, email="guardian@example.com")
    guardian = guardian_factory(organization=organization, user=guardian_user)
    guardian_student_factory(student=student, guardian=guardian)

    due_soon = datetime.date.today() + datetime.timedelta(days=2)
    invoice = invoice_factory(
        student=student, term=term, total_minor=100_000, status="issued", due_date=due_soon
    )

    activate_organization(organization.id)
    reminded = reminder_service.send_reminders_for_organization(organization_id=organization.id)

    assert reminded == 1
    invoice.refresh_from_db()
    assert invoice.reminder_sent_at is not None

    notifications = Notification.all_tenants.filter(ref_type="invoice", ref_id=invoice.id)
    assert notifications.count() == 2
    recipient_ids = {n.recipient_id for n in notifications}
    assert recipient_ids == {student_user.id, guardian_user.id}
    assert all(n.notification_type == "fee_reminder" for n in notifications)
    assert all("due" in n.title.lower() for n in notifications)


@pytest.mark.django_db
def test_reminds_an_overdue_invoice_with_overdue_wording(
    organization, user_factory, school_factory, term_factory, academic_year_factory,
    student_factory, invoice_factory,
):
    school = school_factory(organization=organization)
    term = term_factory(academic_year=academic_year_factory(school=school))
    student_user = user_factory(organization=organization, email="student2@example.com")
    student = student_factory(school=school, user=student_user)

    overdue_date = datetime.date.today() - datetime.timedelta(days=5)
    invoice_factory(student=student, term=term, total_minor=50_000, status="issued", due_date=overdue_date)

    activate_organization(organization.id)
    reminded = reminder_service.send_reminders_for_organization(organization_id=organization.id)

    assert reminded == 1
    notification = Notification.all_tenants.get(recipient=student_user)
    assert "overdue" in notification.title.lower()


@pytest.mark.django_db
def test_does_not_remind_a_fully_paid_invoice(
    organization, user_factory, school_factory, term_factory, academic_year_factory,
    student_factory, invoice_factory, payment_factory,
):
    school = school_factory(organization=organization)
    term = term_factory(academic_year=academic_year_factory(school=school))
    student = student_factory(school=school, user=user_factory(organization=organization, email="s3@example.com"))

    due_soon = datetime.date.today() + datetime.timedelta(days=1)
    invoice = invoice_factory(
        student=student, term=term, total_minor=100_000, status="issued", due_date=due_soon
    )
    payment_factory(invoice=invoice, amount_minor=100_000)

    activate_organization(organization.id)
    reminded = reminder_service.send_reminders_for_organization(organization_id=organization.id)

    assert reminded == 0
    assert Notification.all_tenants.filter(ref_type="invoice", ref_id=invoice.id).count() == 0


@pytest.mark.django_db
def test_does_not_remind_an_invoice_due_far_in_the_future(
    organization, user_factory, school_factory, term_factory, academic_year_factory,
    student_factory, invoice_factory,
):
    school = school_factory(organization=organization)
    term = term_factory(academic_year=academic_year_factory(school=school))
    student = student_factory(school=school, user=user_factory(organization=organization, email="s4@example.com"))

    far_future = datetime.date.today() + datetime.timedelta(days=30)
    invoice_factory(student=student, term=term, total_minor=100_000, status="issued", due_date=far_future)

    activate_organization(organization.id)
    reminded = reminder_service.send_reminders_for_organization(organization_id=organization.id)

    assert reminded == 0


@pytest.mark.django_db
def test_does_not_re_remind_within_the_cooldown_window(
    organization, user_factory, school_factory, term_factory, academic_year_factory,
    student_factory, invoice_factory,
):
    school = school_factory(organization=organization)
    term = term_factory(academic_year=academic_year_factory(school=school))
    student = student_factory(school=school, user=user_factory(organization=organization, email="s5@example.com"))

    overdue_date = datetime.date.today() - datetime.timedelta(days=1)
    invoice = invoice_factory(
        student=student, term=term, total_minor=100_000, status="issued", due_date=overdue_date,
        reminder_sent_at=timezone.now() - datetime.timedelta(days=1),
    )

    activate_organization(organization.id)
    reminded = reminder_service.send_reminders_for_organization(organization_id=organization.id)

    assert reminded == 0
    assert Notification.all_tenants.filter(ref_type="invoice", ref_id=invoice.id).count() == 0


@pytest.mark.django_db
def test_reminds_again_once_the_cooldown_has_elapsed(
    organization, user_factory, school_factory, term_factory, academic_year_factory,
    student_factory, invoice_factory,
):
    school = school_factory(organization=organization)
    term = term_factory(academic_year=academic_year_factory(school=school))
    student = student_factory(school=school, user=user_factory(organization=organization, email="s6@example.com"))

    overdue_date = datetime.date.today() - datetime.timedelta(days=10)
    invoice_factory(
        student=student, term=term, total_minor=100_000, status="issued", due_date=overdue_date,
        reminder_sent_at=timezone.now() - datetime.timedelta(days=8),
    )

    activate_organization(organization.id)
    reminded = reminder_service.send_reminders_for_organization(organization_id=organization.id)

    assert reminded == 1


@pytest.mark.django_db
def test_send_fee_reminders_task_covers_every_active_organization(
    organization, other_organization, user_factory, school_factory, term_factory,
    academic_year_factory, student_factory, invoice_factory,
):
    for org in (organization, other_organization):
        school = school_factory(organization=org)
        term = term_factory(academic_year=academic_year_factory(school=school))
        student = student_factory(
            school=school, user=user_factory(organization=org, email=f"student-{org.id}@example.com")
        )
        overdue_date = datetime.date.today() - datetime.timedelta(days=2)
        invoice_factory(student=student, term=term, total_minor=10_000, status="issued", due_date=overdue_date)

    total = send_fee_reminders.run()

    assert total == 2


@pytest.mark.django_db
def test_send_fee_reminders_management_command_runs_the_same_logic(
    organization, user_factory, school_factory, term_factory, academic_year_factory,
    student_factory, invoice_factory,
):
    school = school_factory(organization=organization)
    term = term_factory(academic_year=academic_year_factory(school=school))
    student = student_factory(school=school, user=user_factory(organization=organization, email="cmd@example.com"))
    overdue_date = datetime.date.today() - datetime.timedelta(days=2)
    invoice_factory(student=student, term=term, total_minor=10_000, status="issued", due_date=overdue_date)

    out = io.StringIO()
    call_command("send_fee_reminders", stdout=out)

    assert "Reminded 1 invoice" in out.getvalue()
