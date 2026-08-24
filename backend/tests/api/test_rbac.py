import pytest
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.accounts.permissions import get_user_permission_codes, require_permission


class _DummyView(APIView):
    permission_classes = [IsAuthenticated, require_permission("widgets.view")]

    def get(self, request):
        return Response({"ok": True})


@pytest.mark.django_db
def test_permission_denied_without_role(organization, user_factory):
    user = user_factory(organization=organization)
    request = APIRequestFactory().get("/")
    force_authenticate(request, user=user)

    response = _DummyView.as_view()(request)

    assert response.status_code == 403


@pytest.mark.django_db
def test_permission_allowed_with_role(organization, user_factory):
    user = user_factory(organization=organization)
    perm = Permission.objects.create(code="widgets.view", module="students", action="view")
    role = Role.objects.create(name="TEACHER", label="Teacher")
    RolePermission.objects.create(role=role, permission=perm)
    UserRole.objects.create(user=user, role=role)

    request = APIRequestFactory().get("/")
    force_authenticate(request, user=user)
    response = _DummyView.as_view()(request)

    assert response.status_code == 200


@pytest.mark.django_db
def test_superuser_bypasses_permission_check(organization, user_factory):
    user = user_factory(organization=organization, is_superuser=True, is_staff=True)
    request = APIRequestFactory().get("/")
    force_authenticate(request, user=user)

    response = _DummyView.as_view()(request)

    assert response.status_code == 200


@pytest.mark.django_db
def test_permission_cache_invalidated_on_grant_and_revoke(organization, user_factory):
    user = user_factory(organization=organization)
    perm = Permission.objects.create(code="fees.refund", module="fees", action="refund")
    role = Role.objects.create(name="FINANCE", label="Finance")
    RolePermission.objects.create(role=role, permission=perm)

    assert "fees.refund" not in get_user_permission_codes(user)

    user_role = UserRole.objects.create(user=user, role=role)
    assert "fees.refund" in get_user_permission_codes(user)

    user_role.delete()
    assert "fees.refund" not in get_user_permission_codes(user)


@pytest.mark.django_db
def test_permission_cache_invalidated_on_role_permission_change(organization, user_factory):
    user = user_factory(organization=organization)
    perm = Permission.objects.create(code="results.approve", module="results", action="approve")
    role = Role.objects.create(name="EXAM_OFFICER", label="Exam Officer")
    UserRole.objects.create(user=user, role=role)

    assert "results.approve" not in get_user_permission_codes(user)

    role_permission = RolePermission.objects.create(role=role, permission=perm)
    assert "results.approve" in get_user_permission_codes(user)

    role_permission.delete()
    assert "results.approve" not in get_user_permission_codes(user)
