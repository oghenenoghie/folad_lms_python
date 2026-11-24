"""Tests for the bootstrap_admin management command (first login on a fresh DB)."""
from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from apps.accounts.management.commands.bootstrap_admin import PASSWORD_ENV_VAR
from apps.accounts.models import User
from apps.tenancy.models import Organization

PASSWORD = "correct horse battery staple"


@pytest.fixture(autouse=True)
def _no_password_env(monkeypatch):
    monkeypatch.delenv(PASSWORD_ENV_VAR, raising=False)


@pytest.mark.django_db
def test_creates_organization_and_superuser_that_can_log_in(api_client):
    output = StringIO()

    call_command("bootstrap_admin", "--email", "admin@example.com", "--password", PASSWORD, stdout=output)

    org = Organization.objects.get(name="Demo School")
    user = User.all_tenants.get(email="admin@example.com")
    assert user.organization_id == org.id
    assert user.is_superuser and user.is_staff and user.is_active
    assert (user.first_name, user.last_name) == ("Admin", "User")
    assert "Created organization 'Demo School'" in output.getvalue()
    assert "Created superuser admin@example.com" in output.getvalue()

    login = api_client.post(
        "/api/v1/auth/login", {"email": "admin@example.com", "password": PASSWORD}, format="json"
    )
    assert login.status_code == 200
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['data']['access']}")
    me = api_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["data"]["email"] == "admin@example.com"
    # Superusers bypass RBAC, so the user can reach the superuser-only admin API.
    assert api_client.get("/api/v1/admin/users").status_code == 200


@pytest.mark.django_db
def test_reuses_existing_organization_with_the_same_name(organization):
    output = StringIO()

    call_command(
        "bootstrap_admin",
        "--email", "owner@example.com",
        "--password", PASSWORD,
        "--org-name", organization.name,
        "--first-name", "Ada",
        "--last-name", "Lovelace",
        stdout=output,
    )

    assert Organization.objects.filter(name=organization.name).count() == 1
    user = User.all_tenants.get(email="owner@example.com")
    assert user.organization_id == organization.id
    assert (user.first_name, user.last_name) == ("Ada", "Lovelace")
    assert f"Using existing organization '{organization.name}'" in output.getvalue()


@pytest.mark.django_db
def test_reads_password_from_environment(monkeypatch):
    monkeypatch.setenv(PASSWORD_ENV_VAR, PASSWORD)

    call_command("bootstrap_admin", "--email", "env@example.com", "--noinput", stdout=StringIO())

    assert User.all_tenants.get(email="env@example.com").check_password(PASSWORD)


@pytest.mark.django_db
def test_refuses_existing_email_without_changing_anything(organization, user_factory):
    existing = user_factory(organization=organization, email="taken@example.com")

    with pytest.raises(CommandError, match="already exists"):
        call_command(
            "bootstrap_admin", "--email", "TAKEN@example.com", "--password", PASSWORD, stdout=StringIO()
        )

    existing.refresh_from_db()
    assert not existing.is_superuser
    assert not Organization.objects.filter(name="Demo School").exists()


@pytest.mark.django_db
def test_rejects_weak_password_before_creating_anything():
    with pytest.raises(CommandError, match="Password rejected"):
        call_command("bootstrap_admin", "--email", "weak@example.com", "--password", "short", stdout=StringIO())

    assert not User.all_tenants.filter(email="weak@example.com").exists()
    assert not Organization.objects.filter(name="Demo School").exists()


@pytest.mark.django_db
def test_requires_a_password_when_not_interactive():
    with pytest.raises(CommandError, match="No password given"):
        call_command("bootstrap_admin", "--email", "nopw@example.com", "--noinput", stdout=StringIO())

    assert not Organization.objects.filter(name="Demo School").exists()
