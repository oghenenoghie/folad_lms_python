import pyotp
import pytest
from django.conf import settings

from apps.accounts.models import FailedLoginAttempt


@pytest.mark.django_db
def test_login_success(api_client, organization, user_factory):
    user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")

    resp = api_client.post(
        "/api/v1/auth/login", {"email": "a@example.com", "password": "s3cret-pass!"}, format="json"
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["access"]
    assert body["data"]["refresh"]


@pytest.mark.django_db
def test_login_wrong_password(api_client, organization, user_factory):
    user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")

    resp = api_client.post(
        "/api/v1/auth/login", {"email": "a@example.com", "password": "wrong"}, format="json"
    )

    assert resp.status_code == 401
    assert FailedLoginAttempt.objects.filter(email="a@example.com").exists()


@pytest.mark.django_db
def test_login_nonexistent_email_does_not_crash(api_client):
    resp = api_client.post(
        "/api/v1/auth/login", {"email": "nobody@example.com", "password": "x"}, format="json"
    )

    assert resp.status_code == 401
    assert FailedLoginAttempt.objects.filter(email="nobody@example.com").exists()


@pytest.mark.django_db
def test_login_lockout_after_threshold(api_client, organization, user_factory):
    user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")

    for _ in range(settings.LOGIN_LOCKOUT_THRESHOLD):
        api_client.post("/api/v1/auth/login", {"email": "a@example.com", "password": "wrong"}, format="json")

    resp = api_client.post(
        "/api/v1/auth/login", {"email": "a@example.com", "password": "s3cret-pass!"}, format="json"
    )
    assert resp.status_code == 423


@pytest.mark.django_db
def test_refresh_rotates_tokens(api_client, organization, user_factory):
    user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    login = api_client.post(
        "/api/v1/auth/login", {"email": "a@example.com", "password": "s3cret-pass!"}, format="json"
    ).json()["data"]

    resp = api_client.post("/api/v1/auth/refresh", {"refresh": login["refresh"]}, format="json")

    assert resp.status_code == 200
    new = resp.json()["data"]
    assert new["access"] != login["access"]
    assert new["refresh"] != login["refresh"]


@pytest.mark.django_db
def test_refresh_reuse_detected_revokes_family(api_client, organization, user_factory):
    user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    login = api_client.post(
        "/api/v1/auth/login", {"email": "a@example.com", "password": "s3cret-pass!"}, format="json"
    ).json()["data"]

    first_refresh = api_client.post(
        "/api/v1/auth/refresh", {"refresh": login["refresh"]}, format="json"
    ).json()["data"]

    # Replay the already-rotated (original) refresh token: reuse detected.
    replay = api_client.post("/api/v1/auth/refresh", {"refresh": login["refresh"]}, format="json")
    assert replay.status_code == 401

    # The legitimately-rotated token must now ALSO be dead: the whole family was revoked.
    followup = api_client.post(
        "/api/v1/auth/refresh", {"refresh": first_refresh["refresh"]}, format="json"
    )
    assert followup.status_code == 401


@pytest.mark.django_db
def test_logout_revokes_refresh_token(api_client, organization, user_factory):
    user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    login = api_client.post(
        "/api/v1/auth/login", {"email": "a@example.com", "password": "s3cret-pass!"}, format="json"
    ).json()["data"]

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    logout = api_client.post("/api/v1/auth/logout", {"refresh": login["refresh"]}, format="json")
    assert logout.status_code == 200

    resp = api_client.post("/api/v1/auth/refresh", {"refresh": login["refresh"]}, format="json")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_me_requires_authentication(api_client):
    resp = api_client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_me_returns_current_user(api_client, organization, user_factory):
    user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    login = api_client.post(
        "/api/v1/auth/login", {"email": "a@example.com", "password": "s3cret-pass!"}, format="json"
    ).json()["data"]

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    resp = api_client.get("/api/v1/auth/me")

    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == "a@example.com"
    assert resp.json()["data"]["student_public_id"] is None


@pytest.mark.django_db
def test_me_exposes_linked_student_public_id(
    api_client, organization, user_factory, school_factory, student_factory
):
    school = school_factory(organization=organization)
    user = user_factory(organization=organization, email="s@example.com", password="s3cret-pass!")
    student = student_factory(school=school, user=user)

    login = api_client.post(
        "/api/v1/auth/login", {"email": "s@example.com", "password": "s3cret-pass!"}, format="json"
    ).json()["data"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")

    resp = api_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["data"]["student_public_id"] == str(student.public_id)
    assert resp.json()["data"]["staff_public_id"] is None
    assert resp.json()["data"]["guardian_public_id"] is None


@pytest.mark.django_db
def test_mfa_enroll_verify_then_required_at_login(api_client, organization, user_factory):
    user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    login = api_client.post(
        "/api/v1/auth/login", {"email": "a@example.com", "password": "s3cret-pass!"}, format="json"
    ).json()["data"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")

    enroll = api_client.post("/api/v1/auth/mfa/enroll")
    assert enroll.status_code == 200
    secret = enroll.json()["data"]["secret"]

    code = pyotp.TOTP(secret).now()
    verify = api_client.post("/api/v1/auth/mfa/verify", {"code": code}, format="json")
    assert verify.status_code == 200

    api_client.credentials()  # clear auth for a fresh login attempt
    no_code = api_client.post(
        "/api/v1/auth/login", {"email": "a@example.com", "password": "s3cret-pass!"}, format="json"
    )
    assert no_code.status_code == 401
    assert "mfa_required" in no_code.json()["errors"]

    with_code = api_client.post(
        "/api/v1/auth/login",
        {"email": "a@example.com", "password": "s3cret-pass!", "totp_code": pyotp.TOTP(secret).now()},
        format="json",
    )
    assert with_code.status_code == 200
