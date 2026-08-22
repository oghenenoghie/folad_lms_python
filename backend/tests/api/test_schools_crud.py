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
def test_school_create_list_retrieve_update_delete(api_client, organization, user_factory):
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "schools.view", "schools.create", "schools.update", "schools.delete")
    _login(api_client, "a@example.com", "s3cret-pass!")

    create = api_client.post("/api/v1/schools", {"name": "Greenwood High", "code": "GH"}, format="json")
    assert create.status_code == 201
    body = create.json()
    assert body["success"] is True
    assert body["data"]["public_id"]
    assert "organization" not in body["data"]
    public_id = body["data"]["public_id"]

    listed = api_client.get("/api/v1/schools")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert listed_body["data"]["pagination"]["total_count"] == 1
    assert listed_body["data"]["results"][0]["public_id"] == public_id

    retrieved = api_client.get(f"/api/v1/schools/{public_id}")
    assert retrieved.status_code == 200
    assert retrieved.json()["data"]["name"] == "Greenwood High"

    updated = api_client.patch(f"/api/v1/schools/{public_id}", {"name": "Greenwood International"}, format="json")
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "Greenwood International"

    deleted = api_client.delete(f"/api/v1/schools/{public_id}")
    assert deleted.status_code == 200

    gone = api_client.get(f"/api/v1/schools/{public_id}")
    assert gone.status_code == 404


@pytest.mark.django_db
def test_school_duplicate_code_returns_conflict_not_crash(api_client, organization, user_factory):
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "schools.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    first = api_client.post("/api/v1/schools", {"name": "Greenwood High", "code": "GH"}, format="json")
    assert first.status_code == 201

    duplicate = api_client.post("/api/v1/schools", {"name": "Greenwood Annex", "code": "GH"}, format="json")
    assert duplicate.status_code == 409
    assert duplicate.json()["success"] is False


@pytest.mark.django_db
def test_school_permission_denied_without_role(api_client, organization, user_factory):
    user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _login(api_client, "a@example.com", "s3cret-pass!")

    resp = api_client.get("/api/v1/schools")

    assert resp.status_code == 403


@pytest.mark.django_db
def test_school_cross_tenant_isolation(api_client, organization, other_organization, user_factory, school_factory):
    school_factory(organization=organization, code="A")
    other_school = school_factory(organization=other_organization, code="B")

    user_b = user_factory(organization=other_organization, email="b@example.com", password="s3cret-pass!")
    _grant(user_b, "schools.view")
    _login(api_client, "b@example.com", "s3cret-pass!")

    listed = api_client.get("/api/v1/schools")
    assert listed.status_code == 200
    results = listed.json()["data"]["results"]
    assert len(results) == 1
    assert results[0]["public_id"] == str(other_school.public_id)

    user_a = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user_a, "schools.view")
    _login(api_client, "a@example.com", "s3cret-pass!")

    cross_tenant_get = api_client.get(f"/api/v1/schools/{other_school.public_id}")
    assert cross_tenant_get.status_code == 404


@pytest.mark.django_db
def test_campus_create_and_list(api_client, organization, user_factory, school_factory):
    school = school_factory(organization=organization)
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "campuses.view", "campuses.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    create = api_client.post(
        "/api/v1/campuses",
        {"school": str(school.public_id), "name": "North Campus", "code": "NC"},
        format="json",
    )
    assert create.status_code == 201

    listed = api_client.get(f"/api/v1/campuses?school_id={school.public_id}")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1


@pytest.mark.django_db
def test_academic_year_create_and_list(api_client, organization, user_factory, school_factory):
    school = school_factory(organization=organization)
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "academic_years.view", "academic_years.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    create = api_client.post(
        "/api/v1/academic-years",
        {
            "school": str(school.public_id),
            "name": "2025/2026",
            "start_date": "2025-09-01",
            "end_date": "2026-07-31",
        },
        format="json",
    )
    assert create.status_code == 201

    listed = api_client.get(f"/api/v1/academic-years?school_id={school.public_id}")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1


@pytest.mark.django_db
def test_term_create_and_list(api_client, organization, user_factory, school_factory, academic_year_factory):
    academic_year = academic_year_factory(school=school_factory(organization=organization))
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "terms.view", "terms.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    create = api_client.post(
        "/api/v1/terms",
        {
            "academic_year": str(academic_year.public_id),
            "name": "First Term",
            "sequence": 1,
            "start_date": "2025-09-01",
            "end_date": "2025-12-15",
        },
        format="json",
    )
    assert create.status_code == 201

    listed = api_client.get(f"/api/v1/terms?academic_year_id={academic_year.public_id}")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1


@pytest.mark.django_db
def test_department_create_and_list(api_client, organization, user_factory, school_factory):
    school = school_factory(organization=organization)
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "departments.view", "departments.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    create = api_client.post(
        "/api/v1/departments",
        {"school": str(school.public_id), "name": "Sciences", "code": "SCI"},
        format="json",
    )
    assert create.status_code == 201

    listed = api_client.get(f"/api/v1/departments?school_id={school.public_id}")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1
