import pytest

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.students.models import Student
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
def test_student_create_list_retrieve_update_delete(api_client, organization, user_factory, school_factory):
    school = school_factory(organization=organization)
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "students.view", "students.create", "students.update", "students.delete")
    _login(api_client, "a@example.com", "s3cret-pass!")

    create = api_client.post(
        "/api/v1/students",
        {
            "school": str(school.public_id),
            "admission_number": "A001",
            "first_name": "Alex",
            "last_name": "Doe",
            "date_of_birth": "2012-01-01",
        },
        format="json",
    )
    assert create.status_code == 201
    body = create.json()
    assert "organization" not in body["data"]
    public_id = body["data"]["public_id"]

    listed = api_client.get(f"/api/v1/students?school_id={school.public_id}")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1

    retrieved = api_client.get(f"/api/v1/students/{public_id}")
    assert retrieved.status_code == 200
    assert retrieved.json()["data"]["enrollment_status"] == "active"

    updated = api_client.patch(
        f"/api/v1/students/{public_id}", {"enrollment_status": "withdrawn"}, format="json"
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["enrollment_status"] == "withdrawn"

    deleted = api_client.delete(f"/api/v1/students/{public_id}")
    assert deleted.status_code == 200

    gone = api_client.get(f"/api/v1/students/{public_id}")
    assert gone.status_code == 404


@pytest.mark.django_db
def test_student_duplicate_admission_number_returns_conflict(
    api_client, organization, user_factory, school_factory
):
    school = school_factory(organization=organization)
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "students.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    payload = {
        "school": str(school.public_id),
        "admission_number": "A001",
        "first_name": "Alex",
        "last_name": "Doe",
        "date_of_birth": "2012-01-01",
    }
    first = api_client.post("/api/v1/students", payload, format="json")
    assert first.status_code == 201

    duplicate = api_client.post(
        "/api/v1/students", {**payload, "first_name": "Alexa"}, format="json"
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["success"] is False


@pytest.mark.django_db
def test_student_permission_denied_without_role(api_client, organization, user_factory):
    user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _login(api_client, "a@example.com", "s3cret-pass!")

    resp = api_client.get("/api/v1/students")

    assert resp.status_code == 403


@pytest.mark.django_db
def test_student_cross_tenant_isolation(
    api_client, organization, other_organization, user_factory, school_factory, student_factory
):
    student_factory(school=school_factory(organization=organization))
    other_student = student_factory(school=school_factory(organization=other_organization))

    user_b = user_factory(organization=other_organization, email="b@example.com", password="s3cret-pass!")
    _grant(user_b, "students.view")
    _login(api_client, "b@example.com", "s3cret-pass!")

    listed = api_client.get("/api/v1/students")
    assert listed.status_code == 200
    results = listed.json()["data"]["results"]
    assert len(results) == 1
    assert results[0]["public_id"] == str(other_student.public_id)


@pytest.mark.django_db
def test_student_app_layer_tenant_isolation(organization, other_organization, school_factory, student_factory):
    student_factory(school=school_factory(organization=organization))
    student_factory(school=school_factory(organization=other_organization))

    activate_organization(organization.id)
    visible = Student.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id
