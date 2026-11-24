import pytest

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.tenancy.context import activate_organization
from apps.transport.models import TransportAssignment


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
def transport_fixture_set(
    organization, school_factory, academic_year_factory, vehicle_factory, transport_route_factory,
    route_stop_factory, student_factory,
):
    school = school_factory(organization=organization)
    academic_year = academic_year_factory(school=school)
    vehicle = vehicle_factory(school=school, capacity=1)
    route = transport_route_factory(school=school)
    stop = route_stop_factory(route=route)
    student = student_factory(school=school)
    return {
        "school": school, "academic_year": academic_year, "vehicle": vehicle, "route": route,
        "stop": stop, "student": student,
    }


@pytest.mark.django_db
def test_assign_transport_rejects_over_capacity(
    api_client, organization, user_factory, transport_fixture_set, student_factory,
):
    vehicle = transport_fixture_set["vehicle"]
    route = transport_fixture_set["route"]
    stop = transport_fixture_set["stop"]
    academic_year = transport_fixture_set["academic_year"]
    student_a = transport_fixture_set["student"]
    student_b = student_factory(school=transport_fixture_set["school"], admission_number="A002")

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "transport_assignments.view", "transport_assignments.create", "transport_assignments.delete")
    _login(api_client, "a@example.com", "s3cret-pass!")

    payload_a = {
        "student": str(student_a.public_id), "vehicle": str(vehicle.public_id),
        "route": str(route.public_id), "stop": str(stop.public_id), "academic_year": str(academic_year.public_id),
    }
    first = api_client.post("/api/v1/transport-assignments", payload_a, format="json")
    assert first.status_code == 201
    first_public_id = first.json()["data"]["public_id"]

    payload_b = {**payload_a, "student": str(student_b.public_id)}
    over_capacity = api_client.post("/api/v1/transport-assignments", payload_b, format="json")
    assert over_capacity.status_code == 409

    unassigned = api_client.delete(f"/api/v1/transport-assignments/{first_public_id}")
    assert unassigned.status_code == 200

    now_fits = api_client.post("/api/v1/transport-assignments", payload_b, format="json")
    assert now_fits.status_code == 201


@pytest.mark.django_db
def test_reassigning_student_deactivates_prior_assignment(
    api_client, organization, user_factory, transport_fixture_set, vehicle_factory,
    transport_route_factory, route_stop_factory,
):
    school = transport_fixture_set["school"]
    academic_year = transport_fixture_set["academic_year"]
    student = transport_fixture_set["student"]
    vehicle_a = transport_fixture_set["vehicle"]
    route_a = transport_fixture_set["route"]
    stop_a = transport_fixture_set["stop"]
    vehicle_b = vehicle_factory(school=school, registration_number="XYZ-999", capacity=5)
    route_b = transport_route_factory(school=school, name="South Route")
    stop_b = route_stop_factory(route=route_b, name="South Gate")

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "transport_assignments.view", "transport_assignments.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    api_client.post(
        "/api/v1/transport-assignments",
        {
            "student": str(student.public_id), "vehicle": str(vehicle_a.public_id),
            "route": str(route_a.public_id), "stop": str(stop_a.public_id),
            "academic_year": str(academic_year.public_id),
        },
        format="json",
    )
    second = api_client.post(
        "/api/v1/transport-assignments",
        {
            "student": str(student.public_id), "vehicle": str(vehicle_b.public_id),
            "route": str(route_b.public_id), "stop": str(stop_b.public_id),
            "academic_year": str(academic_year.public_id),
        },
        format="json",
    )
    assert second.status_code == 201

    activate_organization(organization.id)
    active = TransportAssignment.objects.filter(student=student, academic_year=academic_year, is_active=True)
    assert active.count() == 1
    assert active.first().vehicle_id == vehicle_b.id


@pytest.mark.django_db
def test_transport_app_layer_tenant_isolation(
    organization, other_organization, school_factory, academic_year_factory, vehicle_factory,
    transport_route_factory, route_stop_factory, student_factory, transport_assignment_factory,
):
    school_a = school_factory(organization=organization)
    school_b = school_factory(organization=other_organization)
    ay_a = academic_year_factory(school=school_a)
    ay_b = academic_year_factory(school=school_b)
    vehicle_a = vehicle_factory(school=school_a)
    vehicle_b = vehicle_factory(school=school_b)
    route_a = transport_route_factory(school=school_a)
    route_b = transport_route_factory(school=school_b)
    stop_a = route_stop_factory(route=route_a)
    stop_b = route_stop_factory(route=route_b)
    student_a = student_factory(school=school_a)
    student_b = student_factory(school=school_b)
    transport_assignment_factory(student=student_a, vehicle=vehicle_a, route=route_a, stop=stop_a, academic_year=ay_a)
    transport_assignment_factory(student=student_b, vehicle=vehicle_b, route=route_b, stop=stop_b, academic_year=ay_b)

    activate_organization(organization.id)
    visible = TransportAssignment.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id
