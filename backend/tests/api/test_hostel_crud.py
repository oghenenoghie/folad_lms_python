import pytest

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.hostel.models import HostelAllocation
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


@pytest.fixture
def hostel_fixture_set(
    organization, school_factory, academic_year_factory, hostel_factory, hostel_building_factory,
    hostel_room_factory, hostel_bed_factory, student_factory,
):
    school = school_factory(organization=organization)
    academic_year = academic_year_factory(school=school)
    hostel = hostel_factory(school=school)
    building = hostel_building_factory(hostel=hostel)
    room = hostel_room_factory(building=building)
    bed = hostel_bed_factory(room=room)
    student = student_factory(school=school)
    return {"school": school, "academic_year": academic_year, "bed": bed, "student": student}


@pytest.mark.django_db
def test_allocate_bed_rejects_double_booking_and_vacate_frees_it(
    api_client, organization, user_factory, hostel_fixture_set, student_factory,
):
    bed = hostel_fixture_set["bed"]
    academic_year = hostel_fixture_set["academic_year"]
    student_a = hostel_fixture_set["student"]
    student_b = student_factory(school=hostel_fixture_set["school"], admission_number="A002")

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "hostel_allocations.view", "hostel_allocations.create", "hostel_allocations.update")
    _login(api_client, "a@example.com", "s3cret-pass!")

    first = api_client.post(
        "/api/v1/hostel-allocations",
        {"student": str(student_a.public_id), "bed": str(bed.public_id), "academic_year": str(academic_year.public_id)},
        format="json",
    )
    assert first.status_code == 201
    allocation_public_id = first.json()["data"]["public_id"]

    bed.refresh_from_db()
    assert bed.status == "occupied"

    double_booked = api_client.post(
        "/api/v1/hostel-allocations",
        {"student": str(student_b.public_id), "bed": str(bed.public_id), "academic_year": str(academic_year.public_id)},
        format="json",
    )
    assert double_booked.status_code == 409

    vacated = api_client.post(f"/api/v1/hostel-allocations/{allocation_public_id}/vacate")
    assert vacated.status_code == 200
    assert vacated.json()["data"]["is_active"] is False

    bed.refresh_from_db()
    assert bed.status == "available"

    now_fits = api_client.post(
        "/api/v1/hostel-allocations",
        {"student": str(student_b.public_id), "bed": str(bed.public_id), "academic_year": str(academic_year.public_id)},
        format="json",
    )
    assert now_fits.status_code == 201


@pytest.mark.django_db
def test_hostel_incident_report_and_resolve(
    api_client, organization, user_factory, hostel_fixture_set,
):
    from apps.hostel.models import Hostel

    hostel = Hostel.objects.get(pk=hostel_fixture_set["bed"].room.building.hostel_id)

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "hostel_incidents.view", "hostel_incidents.create", "hostel_incidents.update")
    _login(api_client, "a@example.com", "s3cret-pass!")

    created = api_client.post(
        "/api/v1/hostel-incidents",
        {"hostel": str(hostel.public_id), "description": "Broken window", "severity": "medium", "occurred_at": "2025-09-01T10:00:00Z"},
        format="json",
    )
    assert created.status_code == 201
    incident_public_id = created.json()["data"]["public_id"]
    assert created.json()["data"]["status"] == "open"

    resolved = api_client.post(f"/api/v1/hostel-incidents/{incident_public_id}/resolve")
    assert resolved.status_code == 200
    assert resolved.json()["data"]["status"] == "resolved"


@pytest.mark.django_db
def test_hostel_app_layer_tenant_isolation(
    organization, other_organization, school_factory, academic_year_factory, hostel_factory,
    hostel_building_factory, hostel_room_factory, hostel_bed_factory, student_factory, hostel_allocation_factory,
):
    school_a = school_factory(organization=organization)
    school_b = school_factory(organization=other_organization)
    ay_a = academic_year_factory(school=school_a)
    ay_b = academic_year_factory(school=school_b)
    bed_a = hostel_bed_factory(room=hostel_room_factory(building=hostel_building_factory(hostel=hostel_factory(school=school_a))))
    bed_b = hostel_bed_factory(room=hostel_room_factory(building=hostel_building_factory(hostel=hostel_factory(school=school_b))))
    student_a = student_factory(school=school_a)
    student_b = student_factory(school=school_b)
    hostel_allocation_factory(student=student_a, bed=bed_a, academic_year=ay_a)
    hostel_allocation_factory(student=student_b, bed=bed_b, academic_year=ay_b)

    activate_organization(organization.id)
    visible = HostelAllocation.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id
