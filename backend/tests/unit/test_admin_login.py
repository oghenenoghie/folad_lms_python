"""Django Admin's login page (django-unfold theme) must post `next` back with
the form. Without it, logging in on a directly opened /admin/login/ (no
?next=) falls back to LOGIN_REDIRECT_URL, Django's default
/accounts/profile/, which 404s here. See templates/admin/login.html."""
import re

import pytest

PASSWORD = "s3cret-pass!"


@pytest.fixture
def staff_user(user_factory, organization):
    return user_factory(
        organization=organization, email="admin@example.com", password=PASSWORD,
        is_staff=True, is_superuser=True,
    )


@pytest.fixture(autouse=True)
def _plain_staticfiles_storage(settings):
    # The manifest storage needs collectstatic; see test_admin_dashboard.py.
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


def _posted_next(html: str) -> str | None:
    """The `next` value the browser would submit with the login form."""
    tag = re.search(r'<input[^>]*\bname="next"[^>]*>', html)
    if tag is None or 'form="login-form"' not in tag.group(0):
        return None
    return re.search(r'\bvalue="([^"]*)"', tag.group(0)).group(1)


@pytest.mark.django_db
def test_direct_admin_login_lands_on_admin_index(client, staff_user):
    page = client.get("/admin/login/")
    assert page.status_code == 200
    next_url = _posted_next(page.content.decode())
    assert next_url == "/admin/"

    response = client.post(
        "/admin/login/", {"username": staff_user.email, "password": PASSWORD, "next": next_url}
    )

    assert response.status_code == 302
    assert response["Location"] == "/admin/"


@pytest.mark.django_db
def test_admin_login_keeps_the_requested_next(client):
    page = client.get("/admin/login/?next=/admin/schools/school/")

    assert _posted_next(page.content.decode()) == "/admin/schools/school/"
