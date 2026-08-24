import pytest

from apps.accounts.models import Permission, Role, RolePermission, UserRole


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
            "employee_number": "EMP-100",
            "first_name": "Grace",
            "last_name": "Hopper",
            "position": "Mathematics Teacher",
            "date_joined": "2020-01-01",
        },
        format="json",
    )
    assert create.status_code == 201
    body = create.json()
    assert body["data"]["employment_status"] == "active"
    public_id = body["data"]["public_id"]

    listed = api_client.get(f"/api/v1/staff?school_id={school.public_id}")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1

    updated = api_client.patch(
        f"/api/v1/staff/{public_id}", {"employment_status": "on_leave"}, format="json"
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["employment_status"] == "on_leave"

    deleted = api_client.delete(f"/api/v1/staff/{public_id}")
    assert deleted.status_code == 200


@pytest.mark.django_db
def test_staff_duplicate_employee_number_returns_conflict(
    api_client, organization, user_factory, school_factory
):
    school = school_factory(organization=organization)
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "staff.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    payload = {
        "school": str(school.public_id),
        "employee_number": "EMP-100",
        "first_name": "Grace",
        "last_name": "Hopper",
        "position": "Teacher",
        "date_joined": "2020-01-01",
    }
    first = api_client.post("/api/v1/staff", payload, format="json")
    assert first.status_code == 201

    duplicate = api_client.post("/api/v1/staff", {**payload, "first_name": "Other"}, format="json")
    # `school` and `employee_number` are both serializer-visible fields, so
    # DRF auto-generates a UniqueConstraint validator (400) before ever
    # reaching the service/IntegrityError path — see test_students_crud.py's
    # identical note.
    assert duplicate.status_code == 400
    assert "must make a unique set" in duplicate.json()["non_field_errors"][0]


@pytest.mark.django_db
def test_staff_permission_denied_without_role(api_client, organization, user_factory):
    user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _login(api_client, "a@example.com", "s3cret-pass!")

    resp = api_client.get("/api/v1/staff")

    assert resp.status_code == 403


@pytest.mark.django_db
def test_teacher_create_and_link_to_staff(api_client, organization, user_factory, school_factory, staff_factory):
    staff = staff_factory(school=school_factory(organization=organization))
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "teachers.view", "teachers.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    create = api_client.post(
        "/api/v1/teachers",
        {"staff": str(staff.public_id), "qualification": "B.Sc Mathematics", "specialization": "Algebra"},
        format="json",
    )
    assert create.status_code == 201

    listed = api_client.get(f"/api/v1/teachers?staff_id={staff.public_id}")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1
    assert listed.json()["data"]["results"][0]["specialization"] == "Algebra"


@pytest.mark.django_db
def test_staff_cross_tenant_isolation(
    api_client, organization, other_organization, user_factory, school_factory, staff_factory
):
    staff_factory(school=school_factory(organization=organization))
    other_school = school_factory(organization=other_organization, code="B")
    other_staff = staff_factory(school=other_school, employee_number="EMP-200")

    user_b = user_factory(organization=other_organization, email="b@example.com", password="s3cret-pass!")
    _grant(user_b, "staff.view")
    _login(api_client, "b@example.com", "s3cret-pass!")

    listed = api_client.get("/api/v1/staff")
    assert listed.status_code == 200
    results = listed.json()["data"]["results"]
    assert len(results) == 1
    assert results[0]["public_id"] == str(other_staff.public_id)
