"""Django Admin's login page must send a staff user to the admin index even
when they open /admin/login/ directly (no ?next=).

Stock AdminSite.login puts `next = reverse("admin:index")` in the template
context and contrib.admin's login.html renders it as a hidden input; without
that field LoginView falls back to settings.LOGIN_REDIRECT_URL (unset, so
Django's default /accounts/profile/ — a 404 here). The admin's theme
(django-unfold) ships its own admin/login.html that drops the field, so
templates/admin/login.html adds it back.

These tests submit the form the way a browser would — every field the
rendered page associates with #login-form, plus the credentials — instead
of hand-building the POST, since the bug is precisely about which fields
the page renders."""
from html.parser import HTMLParser

import pytest
from django.urls import reverse

PASSWORD = "s3cret-pass!"


class _LoginFormParser(HTMLParser):
    """Collects #login-form's action and the name/value of every <input>
    the browser would submit with it: those nested inside the form, and
    those outside it that point at it via the HTML `form` attribute."""

    def __init__(self):
        super().__init__()
        self.action = None
        self.fields = {}
        self._in_form = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form" and attrs.get("id") == "login-form":
            self._in_form = True
            self.action = attrs.get("action")
        elif tag == "input" and attrs.get("name"):
            if self._in_form or attrs.get("form") == "login-form":
                self.fields[attrs["name"]] = attrs.get("value") or ""

    def handle_endtag(self, tag):
        if tag == "form":
            self._in_form = False


def _submit_login_form(client, login_url, *, email):
    page = client.get(login_url)
    assert page.status_code == 200
    form = _LoginFormParser()
    form.feed(page.content.decode())
    assert form.action is not None, "admin login page has no #login-form"
    data = {**form.fields, "username": email, "password": PASSWORD}
    return client.post(form.action or login_url, data)


@pytest.fixture
def staff_user(user_factory, organization):
    return user_factory(
        organization=organization, email="admin@example.com", password=PASSWORD,
        is_staff=True, is_superuser=True,
    )


@pytest.fixture(autouse=True)
def _plain_staticfiles_storage(settings):
    # The manifest storage used outside tests needs collectstatic to have
    # run before {% static %} can resolve anything on the rendered page.
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


@pytest.mark.django_db
def test_direct_admin_login_redirects_to_admin_index(client, staff_user):
    response = _submit_login_form(client, reverse("admin:login"), email=staff_user.email)

    assert response.status_code == 302
    assert response["Location"] == reverse("admin:index") == "/admin/"


@pytest.mark.django_db
def test_admin_login_still_honours_next_query_string(client, staff_user):
    target = reverse("admin:accounts_user_changelist")

    response = _submit_login_form(
        client, f"{reverse('admin:login')}?next={target}", email=staff_user.email
    )

    assert response.status_code == 302
    assert response["Location"] == target
