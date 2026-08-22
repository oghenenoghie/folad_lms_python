import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.schools.views import SchoolListCreateView


@pytest.mark.django_db
def test_permission_denied_without_role(organization, user_factory):
    user = user_factory(organization=organization)
    request = APIRequestFactory().get("/")
    force_authenticate(request, user=user)

    response = SchoolListCreateView.as_view()(request)

    assert response.status_code == 403


@pytest.mark.django_db
def test_permission_allowed_with_role(organization, user_factory):
    user = user_factory(organization=organization)
    perm = Permission.objects.get(code="schools.view")
    role = Role.objects.create(name="SCHOOL_VIEWER", label="School Viewer")
    RolePermission.objects.create(role=role, permission=perm)
    UserRole.objects.create(user=user, role=role)

    request = APIRequestFactory().get("/")
    force_authenticate(request, user=user)
    response = SchoolListCreateView.as_view()(request)

    assert response.status_code == 200


@pytest.mark.django_db
def test_superuser_bypasses_permission_check(organization, user_factory):
    user = user_factory(organization=organization, is_superuser=True, is_staff=True)
    request = APIRequestFactory().get("/")
    force_authenticate(request, user=user)

    response = SchoolListCreateView.as_view()(request)

    assert response.status_code == 200
