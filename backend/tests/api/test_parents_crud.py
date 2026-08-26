import pytest

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.parents.models import Guardian
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
def test_guardian_create_list_retrieve_update_delete(api_client, organization, user_factory):
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "guardians.view", "guardians.create", "guardians.update", "guardians.delete")
    _login(api_client, "a@example.com", "s3cret-pass!")

    create = api_client.post(
        "/api/v1/guardians", {"first_name": "Jane", "last_name": "Doe", "phone": "0800000000"}, format="json"
    )
    assert create.status_code == 201
    body = create.json()
    assert body["success"] is True
    assert "organization" not in body["data"]
    public_id = body["data"]["public_id"]

    listed = api_client.get("/api/v1/guardians")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1

    retrieved = api_client.get(f"/api/v1/guardians/{public_id}")
    assert retrieved.status_code == 200
    assert retrieved.json()["data"]["first_name"] == "Jane"

    updated = api_client.patch(f"/api/v1/guardians/{public_id}", {"phone": "0811111111"}, format="json")
    assert updated.status_code == 200
    assert updated.json()["data"]["phone"] == "0811111111"

    deleted = api_client.delete(f"/api/v1/guardians/{public_id}")
    assert deleted.status_code == 200

    gone = api_client.get(f"/api/v1/guardians/{public_id}")
    assert gone.status_code == 404


@pytest.mark.django_db
def test_guardian_permission_denied_without_role(api_client, organization, user_factory):
    user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _login(api_client, "a@example.com", "s3cret-pass!")

    resp = api_client.get("/api/v1/guardians")

    assert resp.status_code == 403


@pytest.mark.django_db
def test_guardian_cross_tenant_isolation(
    api_client, organization, other_organization, user_factory, guardian_factory
):
    guardian_factory(organization=organization, first_name="A")
    other_guardian = guardian_factory(organization=other_organization, first_name="B")

    user_b = user_factory(organization=other_organization, email="b@example.com", password="s3cret-pass!")
    _grant(user_b, "guardians.view")
    _login(api_client, "b@example.com", "s3cret-pass!")

    listed = api_client.get("/api/v1/guardians")
    assert listed.status_code == 200
    results = listed.json()["data"]["results"]
    assert len(results) == 1
    assert results[0]["public_id"] == str(other_guardian.public_id)


@pytest.mark.django_db
def test_guardian_app_layer_tenant_isolation(organization, other_organization, guardian_factory):
    guardian_factory(organization=organization)
    guardian_factory(organization=other_organization)

    activate_organization(organization.id)
    visible = Guardian.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id
