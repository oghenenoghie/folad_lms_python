import io

import pytest
from django.urls import reverse

from apps.academics.models import Enrollment
from apps.parents.models import GuardianStudent
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


def _empty_inline_management_data():
    """The management-form fields Django requires for every inline
    formset on the page, even when no inline row is being filled in —
    StudentAdmin now has two (EnrollmentInline, GuardianStudentInline;
    prefixes come from the FK's own related_name, "enrollments" and
    "guardian_links"). Omitting these doesn't error — it just makes the
    whole page (including the main Student form) silently fail validation
    and re-render with a 200, which is exactly the trap the helper below
    guards every test in this file against.
    """
    data = {}
    for prefix in ("enrollments", "guardian_links"):
        data[f"{prefix}-TOTAL_FORMS"] = "0"
        data[f"{prefix}-INITIAL_FORMS"] = "0"
        data[f"{prefix}-MIN_NUM_FORMS"] = "0"
        data[f"{prefix}-MAX_NUM_FORMS"] = "1000"
    return data


def _post_student_add(client, data, **extra):
    payload = {**_empty_inline_management_data(), **data}
    response = client.post(reverse("admin:students_student_add"), payload, follow=True, **extra)
    if not response.redirect_chain:
        adminform = response.context.get("adminform")
        formsets = response.context.get("inline_admin_formsets", [])
        raise AssertionError(
            "admin add did not redirect (validation failed): "
            f"form errors={adminform.form.errors if adminform else '?'}, "
            f"formset errors={[fs.formset.errors for fs in formsets]}"
        )
    return response


@pytest.mark.django_db
def test_student_admin_add_auto_provisions_login(
    client, superuser, organization, school_factory, settings,
):
    _use_plain_staticfiles_storage(settings)
    school = school_factory(organization=organization, name="Test School", code="TS9")
    client.force_login(superuser)
    activate_organization(None)

    response = _post_student_add(
        client,
        {
            "organization": organization.id, "school": school.id,
            "admission_number": "A200", "first_name": "Ada", "last_name": "Lovelace",
            "date_of_birth": "2012-01-01", "gender": "female", "enrollment_status": "active",
        },
    )

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

    response = _post_student_add(
        client,
        {
            "organization": organization.id, "school": school.id,
            "admission_number": "A201", "first_name": "Kofi", "last_name": "Mensah",
            "email": "dupe@example.com",
            "date_of_birth": "2012-01-01", "gender": "male", "enrollment_status": "active",
        },
    )

    student = Student.all_tenants.get(admission_number="A201")
    assert student.user_id is None

    messages = [str(m) for m in response.context["messages"]]
    assert any("could not be created" in m for m in messages)


@pytest.mark.django_db
def test_student_admin_accepts_a_hand_typed_dash_abbreviated_date(
    client, superuser, organization, school_factory, settings,
):
    """Regression test: the admin's date_of_birth field only accepted the
    plain ISO value its own calendar-picker widget inserts — a staff member
    typing a date by hand in the equally common "02-Aug-2017" style got
    "Enter a valid date" even though the value was perfectly well-formed."""
    _use_plain_staticfiles_storage(settings)
    school = school_factory(organization=organization, name="Test School", code="TS11")
    client.force_login(superuser)
    activate_organization(None)

    response = _post_student_add(
        client,
        {
            "organization": organization.id, "school": school.id,
            "admission_number": "A202", "first_name": "Nia", "last_name": "Okoro",
            "date_of_birth": "02-Aug-2017", "gender": "female", "enrollment_status": "active",
        },
    )

    student = Student.all_tenants.get(admission_number="A202")
    assert str(student.date_of_birth) == "2017-08-02"


@pytest.mark.django_db
def test_student_admin_deleted_at_is_not_a_live_editable_field(
    client, superuser, organization, school_factory, settings,
):
    """Regression test: deleted_at (an internal soft-delete bookkeeping
    field, meant to be set only by student_service.delete_student()) was a
    fully editable widget on the add form — a stray value in it could
    soft-delete a brand-new record on creation, or fail with a spurious
    "enter a valid date" unrelated to anything the operator actually
    meant to fill in."""
    _use_plain_staticfiles_storage(settings)
    school = school_factory(organization=organization, name="Test School", code="TS12")
    client.force_login(superuser)
    activate_organization(None)

    response = client.get(reverse("admin:students_student_add"))

    assert response.status_code == 200
    assert 'name="deleted_at' not in response.content.decode()


@pytest.mark.django_db
def test_student_admin_add_creates_enrollment_and_guardian_link_inline(
    client, superuser, organization, school_factory, campus_factory, class_level_factory,
    class_arm_factory, academic_year_factory, guardian_factory, settings,
):
    """Creating a student, assigning them to a class, and linking a
    guardian should all be possible in the one add-form submission,
    rather than three separate admin visits."""
    _use_plain_staticfiles_storage(settings)
    school = school_factory(organization=organization, name="Test School", code="TS13")
    class_arm = class_arm_factory(class_level=class_level_factory(campus=campus_factory(school=school)))
    academic_year = academic_year_factory(school=school)
    guardian = guardian_factory(organization=organization, first_name="Jane", last_name="Doe")
    client.force_login(superuser)
    activate_organization(None)

    data = {
        "organization": organization.id, "school": school.id,
        "admission_number": "A210", "first_name": "Chidi", "last_name": "Okafor",
        "date_of_birth": "2013-03-01", "gender": "male", "enrollment_status": "active",
        "enrollments-TOTAL_FORMS": "1", "enrollments-INITIAL_FORMS": "0",
        "enrollments-MIN_NUM_FORMS": "0", "enrollments-MAX_NUM_FORMS": "1000",
        "enrollments-0-class_arm": class_arm.id,
        "enrollments-0-academic_year": academic_year.id,
        "enrollments-0-status": "active",
        "enrollments-0-effective_from": "2013-09-01",
        "guardian_links-TOTAL_FORMS": "1", "guardian_links-INITIAL_FORMS": "0",
        "guardian_links-MIN_NUM_FORMS": "0", "guardian_links-MAX_NUM_FORMS": "1000",
        "guardian_links-0-guardian": guardian.id,
        "guardian_links-0-relationship_type": "father",
        "guardian_links-0-is_primary": "on",
    }
    response = client.post(reverse("admin:students_student_add"), data, follow=True)
    assert response.redirect_chain, (
        response.context["adminform"].form.errors,
        [fs.formset.errors for fs in response.context.get("inline_admin_formsets", [])],
    )

    student = Student.all_tenants.get(admission_number="A210")
    enrollment = Enrollment.all_tenants.get(student=student)
    assert enrollment.class_arm_id == class_arm.id
    assert enrollment.organization_id == organization.id

    link = GuardianStudent.all_tenants.get(student=student)
    assert link.guardian_id == guardian.id
    assert link.relationship_type == "father"
    assert link.organization_id == organization.id


@pytest.mark.django_db
def test_student_admin_photo_upload_and_removal(
    client, superuser, organization, school_factory, settings,
):
    _use_plain_staticfiles_storage(settings)
    school = school_factory(organization=organization, name="Test School", code="TS14")
    client.force_login(superuser)
    activate_organization(None)

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (2, 2), color="red").save(buf, format="PNG")
    photo = io.BytesIO(buf.getvalue())
    photo.name = "face.png"

    response = _post_student_add(
        client,
        {
            "organization": organization.id, "school": school.id,
            "admission_number": "A220", "first_name": "Amara", "last_name": "Eze",
            "date_of_birth": "2013-03-01", "gender": "female", "enrollment_status": "active",
            "photo": photo,
        },
    )
    student = Student.all_tenants.get(admission_number="A220")
    assert student.photo_storage_key

    # Removing it (no new file, `remove_photo` checked) clears the key.
    response = client.post(
        reverse("admin:students_student_change", args=[student.pk]),
        {
            **_empty_inline_management_data(),
            "organization": organization.id, "school": school.id,
            "admission_number": "A220", "first_name": "Amara", "last_name": "Eze",
            "date_of_birth": "2013-03-01", "gender": "female", "enrollment_status": "active",
            "remove_photo": "on",
        },
        follow=True,
    )
    assert response.redirect_chain, response.context["adminform"].form.errors
    student.refresh_from_db()
    assert student.photo_storage_key == ""
