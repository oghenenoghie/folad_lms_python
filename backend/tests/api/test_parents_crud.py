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
def test_guardian_create_list_retrieve_update_delete(api_client, organization, user_factory):
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "guardians.view", "guardians.create", "guardians.update", "guardians.delete")
    _login(api_client, "a@example.com", "s3cret-pass!")

    create = api_client.post(
        "/api/v1/guardians",
        {"first_name": "Sam", "last_name": "Okafor", "phone": "+2348012345678"},
        format="json",
    )
    assert create.status_code == 201
    public_id = create.json()["data"]["public_id"]

    listed = api_client.get("/api/v1/guardians")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1

    updated = api_client.patch(
        f"/api/v1/guardians/{public_id}", {"occupation": "Engineer"}, format="json"
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["occupation"] == "Engineer"

    deleted = api_client.delete(f"/api/v1/guardians/{public_id}")
    assert deleted.status_code == 200


@pytest.mark.django_db
def test_guardian_permission_denied_without_role(api_client, organization, user_factory):
    user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _login(api_client, "a@example.com", "s3cret-pass!")

    resp = api_client.get("/api/v1/guardians")

    assert resp.status_code == 403


@pytest.mark.django_db
def test_guardian_student_link_create_and_query_by_both_sides(
    api_client, organization, user_factory, school_factory, student_factory, guardian_factory
):
    student = student_factory(school=school_factory(organization=organization))
    guardian = guardian_factory(organization=organization)
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "guardian_students.view", "guardian_students.create", "guardian_students.delete")
    _login(api_client, "a@example.com", "s3cret-pass!")

    create = api_client.post(
        "/api/v1/guardian-students",
        {
            "guardian": str(guardian.public_id),
            "student": str(student.public_id),
            "relationship_type": "mother",
            "is_primary_contact": True,
        },
        format="json",
    )
    assert create.status_code == 201
    public_id = create.json()["data"]["public_id"]

    by_guardian = api_client.get(f"/api/v1/guardian-students?guardian_id={guardian.public_id}")
    assert by_guardian.status_code == 200
    assert by_guardian.json()["data"]["pagination"]["total_count"] == 1

    by_student = api_client.get(f"/api/v1/guardian-students?student_id={student.public_id}")
    assert by_student.status_code == 200
    assert by_student.json()["data"]["pagination"]["total_count"] == 1
    assert by_student.json()["data"]["results"][0]["relationship_type"] == "mother"

    unlinked = api_client.delete(f"/api/v1/guardian-students/{public_id}")
    assert unlinked.status_code == 200

    after_unlink = api_client.get(f"/api/v1/guardian-students?student_id={student.public_id}")
    assert after_unlink.json()["data"]["pagination"]["total_count"] == 0


@pytest.mark.django_db
def test_guardian_student_duplicate_link_returns_conflict(
    api_client, organization, user_factory, school_factory, student_factory, guardian_factory
):
    student = student_factory(school=school_factory(organization=organization))
    guardian = guardian_factory(organization=organization)
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "guardian_students.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    payload = {"guardian": str(guardian.public_id), "student": str(student.public_id)}
    first = api_client.post("/api/v1/guardian-students", payload, format="json")
    assert first.status_code == 201

    duplicate = api_client.post("/api/v1/guardian-students", payload, format="json")
    # `guardian` and `student` are both serializer-visible fields, so DRF
    # auto-generates a UniqueConstraint validator (400) before ever reaching
    # the service/IntegrityError path — see test_students_crud.py's
    # identical note.
    assert duplicate.status_code == 400
    assert "must make a unique set" in duplicate.json()["non_field_errors"][0]


@pytest.mark.django_db
def test_guardian_cross_tenant_isolation(
    api_client, organization, other_organization, user_factory, guardian_factory
):
    guardian_factory(organization=organization)
    other_guardian = guardian_factory(organization=other_organization, last_name="Other")

    user_b = user_factory(organization=other_organization, email="b@example.com", password="s3cret-pass!")
    _grant(user_b, "guardians.view")
    _login(api_client, "b@example.com", "s3cret-pass!")

    listed = api_client.get("/api/v1/guardians")
    assert listed.status_code == 200
    results = listed.json()["data"]["results"]
    assert len(results) == 1
    assert results[0]["public_id"] == str(other_guardian.public_id)
