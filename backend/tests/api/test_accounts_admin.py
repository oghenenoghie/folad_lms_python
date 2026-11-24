import pytest

from apps.accounts.models import Permission, Role, User, UserRole
from apps.accounts.services.role_admin_service import RoleIsSystemError


def _login(api_client, email, password):
    resp = api_client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    token = resp.json()["data"]["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


@pytest.mark.django_db
def test_non_superuser_blocked_even_with_a_grantable_permission(api_client, organization, user_factory):
    """The whole point of IsSuperUser (see apps.accounts.permissions): a
    normal RBAC permission — even one literally named for this API — must
    never open it, or an org admin could grant themselves control of the
    system that grants permissions."""
    user = user_factory(organization=organization, email="admin@example.com", password="s3cret-pass!")
    role = Role.objects.create(name="ROLE_WOULD_BE_ESCALATION", label="Escalation")
    perm = Permission.objects.create(code="users.view", module="users", action="view")
    role.permissions.add(perm)
    UserRole.objects.create(user=user, role=role)
    _login(api_client, "admin@example.com", "s3cret-pass!")

    for path in ("/api/v1/admin/users", "/api/v1/admin/roles", "/api/v1/admin/permissions"):
        resp = api_client.get(path)
        assert resp.status_code == 403, path


@pytest.mark.django_db
def test_superuser_user_crud_with_role_assignment_and_generated_password(
    api_client, organization, user_factory
):
    user_factory(organization=organization, email="root@example.com", password="s3cret-pass!", is_superuser=True, is_staff=True)
    role = Role.objects.create(name="ROLE_ADMIN_TEST", label="Admin Test", is_system=False)
    _login(api_client, "root@example.com", "s3cret-pass!")

    create = api_client.post(
        "/api/v1/admin/users",
        {
            "email": "newadmin@example.com",
            "first_name": "New",
            "last_name": "Admin",
            "organization": str(organization.public_id),
            "roles": [role.name],
        },
        format="json",
    )
    assert create.status_code == 201
    data = create.json()["data"]
    assert data["roles"] == [role.name]
    password = data["generated_password"]
    assert password and len(password) == 12
    public_id = data["public_id"]

    # the generated password actually works
    api_client.credentials()
    login_resp = api_client.post(
        "/api/v1/auth/login", {"email": "newadmin@example.com", "password": password}, format="json"
    )
    assert login_resp.status_code == 200
    _login(api_client, "root@example.com", "s3cret-pass!")

    listed = api_client.get("/api/v1/admin/users")
    assert listed.status_code == 200
    assert any(row["public_id"] == public_id for row in listed.json()["data"]["results"])

    updated = api_client.patch(
        f"/api/v1/admin/users/{public_id}", {"is_active": False, "roles": []}, format="json"
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["is_active"] is False
    assert updated.json()["data"]["roles"] == []

    deleted = api_client.delete(f"/api/v1/admin/users/{public_id}")
    assert deleted.status_code == 200

    gone = api_client.get(f"/api/v1/admin/users/{public_id}")
    assert gone.status_code == 404


@pytest.mark.django_db
def test_user_and_role_creation_default_to_the_acting_superusers_organization(
    api_client, organization, user_factory
):
    """The frontend has no cross-tenant organization picker (see
    user_admin_service.create_user's docstring), so an admin superuser
    scoped to `organization` creating a user/role with no organization in
    the payload must land in that same organization, not orgless."""
    user_factory(organization=organization, email="root@example.com", password="s3cret-pass!", is_superuser=True, is_staff=True)
    _login(api_client, "root@example.com", "s3cret-pass!")

    user_resp = api_client.post(
        "/api/v1/admin/users", {"email": "defaulted@example.com", "first_name": "D", "last_name": "F"}, format="json"
    )
    assert user_resp.status_code == 201
    created_user = User.all_tenants.get(public_id=user_resp.json()["data"]["public_id"])
    assert created_user.organization_id == organization.id

    role_resp = api_client.post("/api/v1/admin/roles", {"name": "ROLE_DEFAULT_ORG", "label": "Default Org"}, format="json")
    assert role_resp.status_code == 201
    created_role = Role.objects.get(public_id=role_resp.json()["data"]["public_id"])
    assert created_role.organization_id == organization.id


@pytest.mark.django_db
def test_superuser_user_create_with_explicit_password(api_client, organization, user_factory):
    user_factory(organization=organization, email="root@example.com", password="s3cret-pass!", is_superuser=True, is_staff=True)
    _login(api_client, "root@example.com", "s3cret-pass!")

    create = api_client.post(
        "/api/v1/admin/users",
        {
            "email": "chosen@example.com",
            "first_name": "Chosen",
            "last_name": "Pass",
            "password": "MyOwnPassw0rd!",
        },
        format="json",
    )
    assert create.status_code == 201
    assert create.json()["data"]["generated_password"] is None

    api_client.credentials()
    login_resp = api_client.post(
        "/api/v1/auth/login", {"email": "chosen@example.com", "password": "MyOwnPassw0rd!"}, format="json"
    )
    assert login_resp.status_code == 200


@pytest.mark.django_db
def test_superuser_role_crud_with_permission_assignment(api_client, organization, user_factory):
    user_factory(organization=organization, email="root@example.com", password="s3cret-pass!", is_superuser=True, is_staff=True)
    perm_a = Permission.objects.create(code="widgets.view", module="widgets", action="view")
    perm_b = Permission.objects.create(code="widgets.edit", module="widgets", action="edit")
    _login(api_client, "root@example.com", "s3cret-pass!")

    create = api_client.post(
        "/api/v1/admin/roles",
        {"name": "CUSTOM_WIDGET_MANAGER", "label": "Widget Manager", "permissions": ["widgets.view"]},
        format="json",
    )
    assert create.status_code == 201
    data = create.json()["data"]
    assert data["is_system"] is False
    assert data["permissions"] == ["widgets.view"]
    public_id = data["public_id"]

    updated = api_client.patch(
        f"/api/v1/admin/roles/{public_id}",
        {"label": "Widget Super Manager", "permissions": ["widgets.view", "widgets.edit"]},
        format="json",
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["label"] == "Widget Super Manager"
    assert sorted(updated.json()["data"]["permissions"]) == ["widgets.edit", "widgets.view"]

    deleted = api_client.delete(f"/api/v1/admin/roles/{public_id}")
    assert deleted.status_code == 200

    gone = api_client.get(f"/api/v1/admin/roles/{public_id}")
    assert gone.status_code == 404


@pytest.mark.django_db
def test_system_role_cannot_be_edited_or_deleted_via_the_api(api_client, organization, user_factory):
    user_factory(organization=organization, email="root@example.com", password="s3cret-pass!", is_superuser=True, is_staff=True)
    system_role = Role.objects.create(name="ROLE_SYSTEM_TEST", label="System Test", is_system=True)
    _login(api_client, "root@example.com", "s3cret-pass!")

    update = api_client.patch(
        f"/api/v1/admin/roles/{system_role.public_id}", {"label": "Hacked"}, format="json"
    )
    assert update.status_code == 403

    delete = api_client.delete(f"/api/v1/admin/roles/{system_role.public_id}")
    assert delete.status_code == 403

    system_role.refresh_from_db()
    assert system_role.label == "System Test"


@pytest.mark.django_db
def test_role_admin_service_raises_for_is_system_roles_directly():
    from apps.accounts.services import role_admin_service

    role = Role.objects.create(name="ROLE_DIRECT_TEST", label="Direct Test", is_system=True)

    with pytest.raises(RoleIsSystemError):
        role_admin_service.update_role(role=role, actor=None, label="Nope")

    with pytest.raises(RoleIsSystemError):
        role_admin_service.delete_role(role=role, actor=None)


@pytest.mark.django_db
def test_permission_list_is_read_only(api_client, organization, user_factory):
    user_factory(organization=organization, email="root@example.com", password="s3cret-pass!", is_superuser=True, is_staff=True)
    Permission.objects.create(code="widgets.view", module="widgets", action="view")
    _login(api_client, "root@example.com", "s3cret-pass!")

    listed = api_client.get("/api/v1/admin/permissions")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"] is None
    assert any(row["code"] == "widgets.view" for row in listed.json()["data"]["results"])

    created = api_client.post(
        "/api/v1/admin/permissions", {"code": "widgets.new", "module": "widgets", "action": "new"}, format="json"
    )
    assert created.status_code == 405
