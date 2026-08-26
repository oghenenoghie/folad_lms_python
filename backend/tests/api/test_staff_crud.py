import pytest

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.staff.models import Staff
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
def test_staff_create_list_retrieve_update_delete(api_client, organization, user_factory, school_factory):
    school = school_factory(organization=organization)
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "staff.view", "staff.create", "staff.update", "staff.delete")
    _login(api_client, "a@example.com", "s3cret-pass!")

    create = api_client.post(
        "/api/v1/staff",
        {
            "school": str(school.public_id),
            "staff_number": "S001",
            "first_name": "Sam",
            "last_name": "Smith",
        },
        format="json",
    )
    assert create.status_code == 201
    body = create.json()
    assert "organization" not in body["data"]
    public_id = body["data"]["public_id"]

    listed = api_client.get(f"/api/v1/staff?school_id={school.public_id}")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1

    retrieved = api_client.get(f"/api/v1/staff/{public_id}")
    assert retrieved.status_code == 200
    assert retrieved.json()["data"]["employment_status"] == "active"

    updated = api_client.patch(
        f"/api/v1/staff/{public_id}", {"employment_status": "on_leave"}, format="json"
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["employment_status"] == "on_leave"

    deleted = api_client.delete(f"/api/v1/staff/{public_id}")
    assert deleted.status_code == 200

    gone = api_client.get(f"/api/v1/staff/{public_id}")
    assert gone.status_code == 404


@pytest.mark.django_db
def test_staff_duplicate_staff_number_returns_conflict(
    api_client, organization, user_factory, school_factory
):
    school = school_factory(organization=organization)
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "staff.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    payload = {"school": str(school.public_id), "staff_number": "S001", "first_name": "Sam", "last_name": "Smith"}
    first = api_client.post("/api/v1/staff", payload, format="json")
    assert first.status_code == 201

    duplicate = api_client.post("/api/v1/staff", {**payload, "first_name": "Samuel"}, format="json")
    assert duplicate.status_code == 409
    assert duplicate.json()["success"] is False


@pytest.mark.django_db
def test_staff_permission_denied_without_role(api_client, organization, user_factory):
    user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _login(api_client, "a@example.com", "s3cret-pass!")

    resp = api_client.get("/api/v1/staff")

    assert resp.status_code == 403


@pytest.mark.django_db
def test_staff_cross_tenant_isolation(
    api_client, organization, other_organization, user_factory, school_factory, staff_factory
):
    staff_factory(school=school_factory(organization=organization))
    other_staff = staff_factory(school=school_factory(organization=other_organization))

    user_b = user_factory(organization=other_organization, email="b@example.com", password="s3cret-pass!")
    _grant(user_b, "staff.view")
    _login(api_client, "b@example.com", "s3cret-pass!")

    listed = api_client.get("/api/v1/staff")
    assert listed.status_code == 200
    results = listed.json()["data"]["results"]
    assert len(results) == 1
    assert results[0]["public_id"] == str(other_staff.public_id)


@pytest.mark.django_db
def test_staff_app_layer_tenant_isolation(organization, other_organization, school_factory, staff_factory):
    staff_factory(school=school_factory(organization=organization))
    staff_factory(school=school_factory(organization=other_organization))

    activate_organization(organization.id)
    visible = Staff.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id


@pytest.mark.django_db
def test_teacher_profile_create_list_retrieve_delete(
    api_client, organization, user_factory, school_factory, staff_factory
):
    staff = staff_factory(school=school_factory(organization=organization))
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "teachers.view", "teachers.create", "teachers.delete")
    _login(api_client, "a@example.com", "s3cret-pass!")

    create = api_client.post(
        "/api/v1/teachers",
        {"staff": str(staff.public_id), "qualification": "B.Ed", "specialization": "Mathematics"},
        format="json",
    )
    assert create.status_code == 201
    public_id = create.json()["data"]["public_id"]

    listed = api_client.get("/api/v1/teachers")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1

    duplicate = api_client.post(
        "/api/v1/teachers", {"staff": str(staff.public_id), "qualification": "M.Ed"}, format="json"
    )
    assert duplicate.status_code == 409

    deleted = api_client.delete(f"/api/v1/teachers/{public_id}")
    assert deleted.status_code == 200
