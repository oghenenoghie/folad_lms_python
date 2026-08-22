import pytest
from django.db import connection

from apps.schools.models import AcademicYear, Campus, Department, School, Term
from apps.tenancy.context import activate_organization


def _seed_school(organization, *, code="TS"):
    activate_organization(organization.id)
    return School.all_tenants.create(organization=organization, name="Test School", code=code)


@pytest.mark.django_db
def test_no_context_fails_closed(organization):
    _seed_school(organization)

    activate_organization(None)

    assert list(School.objects.all()) == []


@pytest.mark.django_db
def test_app_layer_tenant_isolation(organization, other_organization):
    _seed_school(organization)
    _seed_school(other_organization)

    activate_organization(organization.id)
    visible = School.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id


@pytest.mark.skipif(connection.vendor != "postgresql", reason="RLS is Postgres-only")
@pytest.mark.django_db
def test_rls_blocks_cross_tenant_read_at_db_level(organization, other_organization):
    """Proves the DB-level defence-in-depth layer independently of any
    Django manager: a raw, unfiltered SQL query is still constrained by
    the `app.current_org` GUC via the RLS policy on schools_school.
    """
    _seed_school(organization, code="A")
    _seed_school(other_organization, code="B")
    _seed_school(organization, code="C")

    activate_organization(organization.id)
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM schools_school")
        (count,) = cursor.fetchone()

    assert count == 2  # only org A's rows, even with zero WHERE-clause filtering


@pytest.mark.skipif(connection.vendor != "postgresql", reason="RLS is Postgres-only")
@pytest.mark.django_db
def test_rls_blocks_all_rows_with_sentinel_context(organization):
    _seed_school(organization)

    activate_organization(None)  # writes the '0' sentinel — matches no real org
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM schools_school")
        (count,) = cursor.fetchone()

    assert count == 0


@pytest.mark.django_db
def test_campus_app_layer_tenant_isolation(organization, other_organization, school_factory, campus_factory):
    school_a = school_factory(organization=organization)
    school_b = school_factory(organization=other_organization)
    campus_factory(school=school_a)
    campus_factory(school=school_b)

    activate_organization(organization.id)
    visible = Campus.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id


@pytest.mark.django_db
def test_academic_year_app_layer_tenant_isolation(
    organization, other_organization, school_factory, academic_year_factory
):
    school_a = school_factory(organization=organization)
    school_b = school_factory(organization=other_organization)
    academic_year_factory(school=school_a)
    academic_year_factory(school=school_b)

    activate_organization(organization.id)
    visible = AcademicYear.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id


@pytest.mark.django_db
def test_term_app_layer_tenant_isolation(
    organization, other_organization, school_factory, academic_year_factory, term_factory
):
    year_a = academic_year_factory(school=school_factory(organization=organization))
    year_b = academic_year_factory(school=school_factory(organization=other_organization))
    term_factory(academic_year=year_a)
    term_factory(academic_year=year_b)

    activate_organization(organization.id)
    visible = Term.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id


@pytest.mark.django_db
def test_department_app_layer_tenant_isolation(
    organization, other_organization, school_factory, department_factory
):
    school_a = school_factory(organization=organization)
    school_b = school_factory(organization=other_organization)
    department_factory(school=school_a)
    department_factory(school=school_b)

    activate_organization(organization.id)
    visible = Department.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id
