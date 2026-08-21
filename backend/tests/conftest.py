import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def organization(db):
    from apps.tenancy.models import Organization

    return Organization.objects.create(name="Test Org")


@pytest.fixture
def other_organization(db):
    from apps.tenancy.models import Organization

    return Organization.objects.create(name="Other Org")


@pytest.fixture
def user_factory(db):
    from apps.accounts.models import User

    def make(*, organization, email="user@example.com", password="correct horse battery staple", **extra):
        return User.objects.create_user(
            email=email, password=password, first_name="Test", last_name="User",
            organization=organization, **extra,
        )

    return make
