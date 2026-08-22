import pytest

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.schools.models import AcademicYear
from apps.schools.services.academic_year_service import activate_academic_year
from apps.schools.services.term_service import activate_term
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
def test_activate_academic_year_unsets_previous_current(organization, user_factory, school_factory, academic_year_factory):
    school = school_factory(organization=organization)
    year_a = academic_year_factory(school=school, name="2024/2025", is_current=True)
    year_b = academic_year_factory(school=school, name="2025/2026")
    actor = user_factory(organization=organization)

    activate_organization(organization.id)
    activate_academic_year(academic_year=year_b, actor=actor)

    year_a.refresh_from_db()
    year_b.refresh_from_db()
    assert year_a.is_current is False
    assert year_b.is_current is True


@pytest.mark.django_db
def test_activate_term_unsets_previous_current(organization, user_factory, school_factory, academic_year_factory, term_factory):
    year = academic_year_factory(school=school_factory(organization=organization))
    term_a = term_factory(academic_year=year, name="First Term", sequence=1, is_current=True)
    term_b = term_factory(academic_year=year, name="Second Term", sequence=2)
    actor = user_factory(organization=organization)

    activate_organization(organization.id)
    activate_term(term=term_b, actor=actor)

    term_a.refresh_from_db()
    term_b.refresh_from_db()
    assert term_a.is_current is False
    assert term_b.is_current is True


@pytest.mark.django_db
def test_activate_academic_year_endpoint(api_client, organization, user_factory, school_factory, academic_year_factory):
    school = school_factory(organization=organization)
    year_a = academic_year_factory(school=school, name="2024/2025", is_current=True)
    year_b = academic_year_factory(school=school, name="2025/2026")
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "academic_years.update")
    _login(api_client, "a@example.com", "s3cret-pass!")

    resp = api_client.post(f"/api/v1/academic-years/{year_b.public_id}/activate")

    assert resp.status_code == 200
    assert resp.json()["data"]["is_current"] is True
    assert AcademicYear.objects.get(pk=year_a.pk).is_current is False
