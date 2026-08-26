import pytest
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def _clear_cache():
    """Redis isn't reset between test runs the way the Postgres test DB is
    (which is recreated fresh, resetting PK sequences to 1 each run) — a
    stale permissions cache entry (accounts.cache_keys: `perms:<user_id>:
    <org_id>`) from an earlier run can collide with a freshly created user
    that happens to get the same low ID, silently granting permissions that
    were never actually assigned in this run."""
    from django.core.cache import cache

    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def organization(db):
    from apps.tenancy.models import Organization

    return Organization.objects.create(name="Test Org")


@pytest.fixture
def other_organization(db):
    from apps.tenancy.models import Organization

    return Organization.objects.create(name="Other Org")


@pytest.fixture
def user_factory(db):
    from apps.accounts.models import User

    def make(*, organization, email="user@example.com", password="correct horse battery staple", **extra):
        return User.objects.create_user(
            email=email, password=password, first_name="Test", last_name="User",
            organization=organization, **extra,
        )

    return make


@pytest.fixture
def school_factory(db):
    from apps.schools.models import School
    from apps.tenancy.context import activate_organization

    def make(*, organization, name="Test School", code="TS", **extra):
        activate_organization(organization.id)
        return School.all_tenants.create(organization=organization, name=name, code=code, **extra)

    return make


@pytest.fixture
def campus_factory(db):
    from apps.schools.models import Campus
    from apps.tenancy.context import activate_organization

    def make(*, school, name="Main Campus", code="MC", **extra):
        activate_organization(school.organization_id)
        return Campus.all_tenants.create(
            organization=school.organization, school=school, name=name, code=code, **extra
        )

    return make


@pytest.fixture
def academic_year_factory(db):
    from apps.schools.models import AcademicYear
    from apps.tenancy.context import activate_organization

    def make(*, school, name="2025/2026", start_date="2025-09-01", end_date="2026-07-31", **extra):
        activate_organization(school.organization_id)
        return AcademicYear.all_tenants.create(
            organization=school.organization,
            school=school,
            name=name,
            start_date=start_date,
            end_date=end_date,
            **extra,
        )

    return make


@pytest.fixture
def term_factory(db):
    from apps.schools.models import Term
    from apps.tenancy.context import activate_organization

    def make(*, academic_year, name="First Term", sequence=1, start_date="2025-09-01", end_date="2025-12-15", **extra):
        activate_organization(academic_year.organization_id)
        return Term.all_tenants.create(
            organization=academic_year.organization,
            academic_year=academic_year,
            name=name,
            sequence=sequence,
            start_date=start_date,
            end_date=end_date,
            **extra,
        )

    return make


@pytest.fixture
def department_factory(db):
    from apps.schools.models import Department
    from apps.tenancy.context import activate_organization

    def make(*, school, name="Sciences", code="SCI", **extra):
        activate_organization(school.organization_id)
        return Department.all_tenants.create(
            organization=school.organization, school=school, name=name, code=code, **extra
        )

    return make


@pytest.fixture
def guardian_factory(db):
    from apps.parents.models import Guardian
    from apps.tenancy.context import activate_organization

    def make(*, organization, first_name="Jane", last_name="Doe", **extra):
        activate_organization(organization.id)
        return Guardian.all_tenants.create(
            organization=organization, first_name=first_name, last_name=last_name, **extra
        )

    return make


@pytest.fixture
def student_factory(db):
    from apps.students.models import Student
    from apps.tenancy.context import activate_organization

    def make(
        *,
        school,
        admission_number="A001",
        first_name="Alex",
        last_name="Doe",
        date_of_birth="2012-01-01",
        **extra,
    ):
        activate_organization(school.organization_id)
        return Student.all_tenants.create(
            organization=school.organization,
            school=school,
            admission_number=admission_number,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            **extra,
        )

    return make


@pytest.fixture
def guardian_student_factory(db):
    from apps.students.models import GuardianStudent
    from apps.tenancy.context import activate_organization

    def make(*, student, guardian, relationship_type="guardian", **extra):
        activate_organization(student.organization_id)
        return GuardianStudent.all_tenants.create(
            organization=student.organization,
            student=student,
            guardian=guardian,
            relationship_type=relationship_type,
            **extra,
        )

    return make


@pytest.fixture
def staff_factory(db):
    from apps.staff.models import Staff
    from apps.tenancy.context import activate_organization

    def make(*, school, staff_number="S001", first_name="Sam", last_name="Smith", **extra):
        activate_organization(school.organization_id)
        return Staff.all_tenants.create(
            organization=school.organization,
            school=school,
            staff_number=staff_number,
            first_name=first_name,
            last_name=last_name,
            **extra,
        )

    return make


@pytest.fixture
def teacher_factory(db):
    from apps.staff.models import Teacher
    from apps.tenancy.context import activate_organization

    def make(*, staff, **extra):
        activate_organization(staff.organization_id)
        return Teacher.all_tenants.create(organization=staff.organization, staff=staff, **extra)

    return make
