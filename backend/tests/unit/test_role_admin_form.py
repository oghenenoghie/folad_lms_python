import pytest
from django.urls import reverse

from apps.accounts.models import Permission, Role, RolePermission


@pytest.fixture
def superuser(user_factory, organization):
    return user_factory(
        organization=organization, email="admin@example.com", password="s3cret-pass!",
        is_staff=True, is_superuser=True,
    )


@pytest.mark.django_db
def test_role_admin_change_form_lists_all_permissions_as_multi_select(client, superuser, settings):
    # The real (manifest-hashed) staticfiles storage requires `collectstatic`
    # to have run, which this test suite never does — swap in the plain
    # storage so rendering the actual admin page doesn't need that.
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    client.force_login(superuser)
    perm_a = Permission.objects.create(code="widgets.view", module="widgets", action="view")
    perm_b = Permission.objects.create(code="widgets.create", module="widgets", action="create")

    response = client.get(reverse("admin:accounts_role_add"))

    assert response.status_code == 200
    form = response.context["adminform"].form
    available_ids = set(form.fields["permissions"].queryset.values_list("id", flat=True))
    assert {perm_a.id, perm_b.id} <= available_ids
    assert form.fields["permissions"].widget.allow_multiple_selected


@pytest.mark.django_db
def test_role_admin_create_saves_multiple_selected_permissions(client, superuser):
    client.force_login(superuser)
    perm_a = Permission.objects.create(code="widgets.view", module="widgets", action="view")
    perm_b = Permission.objects.create(code="widgets.create", module="widgets", action="create")

    response = client.post(
        reverse("admin:accounts_role_add"),
        {"name": "WIDGET_MANAGER", "label": "Widget Manager", "is_system": "on", "permissions": [perm_a.id, perm_b.id]},
    )

    assert response.status_code == 302, response.context["adminform"].form.errors if response.status_code == 200 else None
    role = Role.objects.get(name="WIDGET_MANAGER")
    assert set(role.permissions.values_list("id", flat=True)) == {perm_a.id, perm_b.id}
    assert RolePermission.objects.filter(role=role).count() == 2


@pytest.mark.django_db
def test_role_admin_edit_updates_permission_selection(client, superuser):
    client.force_login(superuser)
    perm_a = Permission.objects.create(code="widgets.view", module="widgets", action="view")
    perm_b = Permission.objects.create(code="widgets.create", module="widgets", action="create")
    role = Role.objects.create(name="WIDGET_MANAGER", label="Widget Manager")
    RolePermission.objects.create(role=role, permission=perm_a)

    response = client.post(
        reverse("admin:accounts_role_change", args=[role.pk]),
        {"name": role.name, "label": role.label, "is_system": "on", "permissions": [perm_b.id]},
    )

    assert response.status_code == 302
    role.refresh_from_db()
    assert list(role.permissions.values_list("id", flat=True)) == [perm_b.id]
