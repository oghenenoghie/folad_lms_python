import pytest
from django.urls import reverse

from apps.accounts.models import Role, UserRole
from apps.schools.models import Department
from apps.tenancy.context import activate_organization


@pytest.fixture
def superuser(user_factory, organization):
    return user_factory(
        organization=organization, email="admin@example.com", password="s3cret-pass!",
        is_staff=True, is_superuser=True,
    )


def _use_plain_staticfiles_storage(settings):
    # The real (manifest-hashed) staticfiles storage requires `collectstatic`
    # to have run, which this test suite never does — swap in the plain
    # storage so rendering a re-displayed (validation-error) admin page
    # doesn't need that. A full reassignment (not an in-place mutation) so
    # Django's setting_changed signal actually fires and invalidates the
    # cached storage instance.
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


@pytest.mark.django_db
def test_department_admin_add_accepts_existing_school_with_no_ambient_org_context(
    client, superuser, organization, school_factory, settings,
):
    """Regression test: DepartmentAdmin's "school" field validated against
    School.objects (a TenantManager) rather than School.all_tenants, so it
    always rejected the submitted value in a real admin session — which,
    unlike the JWT API, never activates an organization's RLS context."""
    _use_plain_staticfiles_storage(settings)
    school = school_factory(organization=organization, name="Test School", code="TS1")
    client.force_login(superuser)
    activate_organization(None)

    response = client.post(
        reverse("admin:schools_department_add"),
        {
            "organization": organization.id, "school": school.id,
            "name": "Sciences", "code": "SCI", "is_active": "on",
        },
    )

    assert response.status_code == 302, (
        response.context["adminform"].form.errors if response.status_code == 200 else response.status_code
    )
    dept = Department.all_tenants.get(code="SCI")
    assert dept.school_id == school.id


@pytest.mark.django_db
def test_department_admin_rejects_duplicate_school_code_with_form_error_not_500(
    client, superuser, organization, school_factory, department_factory, settings,
):
    """Regression test: Department.validate_unique() checked the (school,
    code) UniqueConstraint via Department.objects (a TenantManager), which
    returns empty with no organization context active — so a genuine
    duplicate silently "validated" as unique in Django Admin and only
    failed once the real, unscoped database constraint rejected the insert,
    crashing with a raw IntegrityError (500) instead of a normal form
    error."""
    _use_plain_staticfiles_storage(settings)
    school = school_factory(organization=organization, name="Test School", code="TS2")
    department_factory(school=school, name="Sciences", code="SCI")
    client.force_login(superuser)
    activate_organization(None)

    response = client.post(
        reverse("admin:schools_department_add"),
        {
            "organization": organization.id, "school": school.id,
            "name": "Sciences Again", "code": "SCI", "is_active": "on",
        },
    )

    assert response.status_code == 200
    assert "already exists" in str(response.context["adminform"].form.errors)
    assert Department.all_tenants.filter(school=school, code="SCI").count() == 1


@pytest.mark.django_db
def test_user_role_admin_add_accepts_existing_user_with_no_ambient_org_context(
    client, superuser, organization, user_factory, settings,
):
    """Regression test: UserRoleAdmin's "user"/"granted_by" fields point at
    the tenant-scoped User model but UserRoleAdmin didn't use any tenant-
    aware mixin, so selecting an existing user always failed to save."""
    _use_plain_staticfiles_storage(settings)
    target_user = user_factory(organization=organization, email="teacher@example.com")
    role = Role.objects.create(name="TEACHER_ROLE", label="Teacher")
    client.force_login(superuser)
    activate_organization(None)

    response = client.post(
        reverse("admin:accounts_userrole_add"),
        {"user": target_user.id, "role": role.id},
    )

    assert response.status_code == 302, (
        response.context["adminform"].form.errors if response.status_code == 200 else response.status_code
    )
    assert UserRole.objects.filter(user=target_user, role=role).exists()
