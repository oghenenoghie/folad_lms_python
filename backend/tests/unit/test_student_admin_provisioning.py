import pytest
from django.urls import reverse

from apps.students.models import Student
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
def test_student_admin_add_auto_provisions_login(
    client, superuser, organization, school_factory, settings,
):
    _use_plain_staticfiles_storage(settings)
    school = school_factory(organization=organization, name="Test School", code="TS9")
    client.force_login(superuser)
    activate_organization(None)

    response = client.post(
        reverse("admin:students_student_add"),
        {
            "organization": organization.id, "school": school.id,
            "admission_number": "A200", "first_name": "Ada", "last_name": "Lovelace",
            "date_of_birth": "2012-01-01", "gender": "female", "enrollment_status": "active",
        },
        follow=True,
    )

    assert response.status_code == 200
    student = Student.all_tenants.get(admission_number="A200")
    assert student.user_id is not None
    assert student.user.email.endswith("@students.local")

    messages = [str(m) for m in response.context["messages"]]
    assert any("Login created" in m for m in messages)


@pytest.mark.django_db
def test_student_admin_add_with_email_reuses_it_and_reports_conflict(
    client, superuser, organization, school_factory, user_factory, settings,
):
    _use_plain_staticfiles_storage(settings)
    school = school_factory(organization=organization, name="Test School", code="TS10")
    user_factory(organization=organization, email="dupe@example.com")
    client.force_login(superuser)
    activate_organization(None)

    response = client.post(
        reverse("admin:students_student_add"),
        {
            "organization": organization.id, "school": school.id,
            "admission_number": "A201", "first_name": "Kofi", "last_name": "Mensah",
            "email": "dupe@example.com",
            "date_of_birth": "2012-01-01", "gender": "male", "enrollment_status": "active",
        },
        follow=True,
    )

    assert response.status_code == 200
    student = Student.all_tenants.get(admission_number="A201")
    assert student.user_id is None

    messages = [str(m) for m in response.context["messages"]]
    assert any("could not be created" in m for m in messages)
