import pytest
from django.db import connection

from apps.accounts.models import LoginHistory
from apps.tenancy.context import activate_organization, get_current_organization_id


def _seed_login_history(organization, user):
    """RLS's WITH CHECK requires the row being inserted to match the
    currently active org — exactly as real app code always does (auth_service
    activates the org before writing LoginHistory)."""
    activate_organization(organization.id)
    LoginHistory.all_tenants.create(user=user, organization=organization, success=True)


@pytest.mark.django_db
def test_no_context_fails_closed(organization, user_factory):
    user = user_factory(organization=organization)
    _seed_login_history(organization, user)

    activate_organization(None)

    assert list(LoginHistory.objects.all()) == []


@pytest.mark.django_db
def test_app_layer_tenant_isolation(organization, other_organization, user_factory):
    user_a = user_factory(organization=organization, email="a@example.com")
    user_b = user_factory(organization=other_organization, email="b@example.com")
    _seed_login_history(organization, user_a)
    _seed_login_history(other_organization, user_b)

    activate_organization(organization.id)
    visible = LoginHistory.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id


@pytest.mark.django_db
def test_context_resets_between_activations(organization, other_organization):
    activate_organization(organization.id)
    assert get_current_organization_id() == organization.id

    activate_organization(other_organization.id)
    assert get_current_organization_id() == other_organization.id

    activate_organization(None)
    assert get_current_organization_id() is None


@pytest.mark.skipif(connection.vendor != "postgresql", reason="RLS is Postgres-only")
@pytest.mark.django_db
def test_rls_blocks_cross_tenant_read_at_db_level(organization, other_organization, user_factory):
    """Proves the DB-level defence-in-depth layer independently of any
    Django manager: a raw, unfiltered SQL query is still constrained by
    the `app.current_org` GUC via the RLS policy on accounts_login_history.
    """
    user_a = user_factory(organization=organization, email="a@example.com")
    user_b = user_factory(organization=other_organization, email="b@example.com")
    _seed_login_history(organization, user_a)
    _seed_login_history(other_organization, user_b)
    _seed_login_history(organization, user_a)

    activate_organization(organization.id)
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM accounts_login_history")
        (count,) = cursor.fetchone()

    assert count == 2  # only org A's rows, even with zero WHERE-clause filtering


@pytest.mark.skipif(connection.vendor != "postgresql", reason="RLS is Postgres-only")
@pytest.mark.django_db
def test_rls_blocks_all_rows_with_sentinel_context(organization, other_organization, user_factory):
    user_a = user_factory(organization=organization, email="a@example.com")
    _seed_login_history(organization, user_a)

    activate_organization(None)  # writes the '0' sentinel — matches no real org
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM accounts_login_history")
        (count,) = cursor.fetchone()

    assert count == 0
