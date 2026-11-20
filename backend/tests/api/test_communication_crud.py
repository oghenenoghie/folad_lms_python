import pytest

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.communication.models import Message, Notification
from apps.tenancy.context import activate_organization


def _grant(user, *codes):
    role = Role.objects.create(name=f"ROLE_{user.pk}_{'_'.join(codes)}"[:100], label="Test Role")
    for code in codes:
        RolePermission.objects.create(role=role, permission=Permission.objects.get(code=code))
    UserRole.objects.create(user=user, role=role)


def _login(api_client, email, password):
    resp = api_client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    token = resp.json()["data"]["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


@pytest.mark.django_db
def test_publishing_announcement_notifies_its_audience(
    api_client, organization, user_factory, school_factory, student_factory,
):
    school = school_factory(organization=organization)
    student = student_factory(school=school)
    student_user = user_factory(
        organization=organization, email="student@example.com", password="s3cret-pass!"
    )
    student.user = student_user
    student.save(update_fields=["user"])
    staff_user = user_factory(organization=organization, email="staff@example.com", password="s3cret-pass!")

    admin_user = user_factory(organization=organization, email="admin@example.com", password="s3cret-pass!")
    _grant(admin_user, "announcements.view", "announcements.create", "announcements.update")
    _login(api_client, "admin@example.com", "s3cret-pass!")

    created = api_client.post(
        "/api/v1/announcements",
        {"school": str(school.public_id), "title": "Sports Day", "body": "Next Friday", "audience": "students"},
        format="json",
    )
    assert created.status_code == 201
    announcement_public_id = created.json()["data"]["public_id"]

    published = api_client.post(f"/api/v1/announcements/{announcement_public_id}/publish")
    assert published.status_code == 200
    assert published.json()["data"]["published_at"] is not None

    student_notifications = Notification.objects.filter(recipient=student_user)
    assert student_notifications.count() == 1
    assert student_notifications.first().title == "Sports Day"

    staff_notifications = Notification.objects.filter(recipient=staff_user)
    assert staff_notifications.count() == 0


@pytest.mark.django_db
def test_notification_list_and_mark_read(api_client, organization, user_factory, notification_factory):
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    notification = notification_factory(recipient=user, title="Welcome")
    _login(api_client, "a@example.com", "s3cret-pass!")

    listed = api_client.get("/api/v1/notifications")
    assert listed.status_code == 200
    assert len(listed.json()["data"]["results"]) == 1

    marked = api_client.post(f"/api/v1/notifications/{notification.public_id}/read")
    assert marked.status_code == 200
    assert marked.json()["data"]["is_read"] is True

    unread = api_client.get("/api/v1/notifications?is_read=false")
    assert len(unread.json()["data"]["results"]) == 0


@pytest.mark.django_db
def test_notification_preferences_get_and_patch(api_client, organization, user_factory):
    user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _login(api_client, "a@example.com", "s3cret-pass!")

    initial = api_client.get("/api/v1/notification-preferences")
    assert initial.status_code == 200
    assert initial.json()["data"]["email_enabled"] is True

    updated = api_client.patch(
        "/api/v1/notification-preferences", {"sms_enabled": True, "push_enabled": False}, format="json"
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["sms_enabled"] is True
    assert updated.json()["data"]["push_enabled"] is False


@pytest.mark.django_db
def test_message_send_and_mark_read(api_client, organization):
    from apps.accounts.models import User

    User.objects.create_user(
        email="a@example.com", password="s3cret-pass!", first_name="Ada", last_name="Okafor",
        organization=organization,
    )
    recipient = User.objects.create_user(
        email="b@example.com", password="s3cret-pass!", first_name="Femi", last_name="Adeyemi",
        organization=organization,
    )
    _login(api_client, "a@example.com", "s3cret-pass!")

    sent = api_client.post(
        "/api/v1/messages",
        {"recipient": str(recipient.public_id), "subject": "Hi", "body": "How are you?"},
        format="json",
    )
    assert sent.status_code == 201
    body = sent.json()["data"]
    message_public_id = body["public_id"]
    # sender/recipient are opaque public_ids with no accessible lookup
    # endpoint to resolve them to a name — sender_name/recipient_name
    # exist precisely so the inbox UI has something to display.
    assert body["sender_name"] == "Ada Okafor"
    assert body["recipient_name"] == "Femi Adeyemi"

    api_client.credentials()
    _login(api_client, "b@example.com", "s3cret-pass!")
    inbox = api_client.get("/api/v1/messages")
    assert inbox.status_code == 200
    assert len(inbox.json()["data"]["results"]) == 1
    assert inbox.json()["data"]["results"][0]["sender_name"] == "Ada Okafor"

    marked = api_client.post(f"/api/v1/messages/{message_public_id}/read")
    assert marked.status_code == 200
    assert marked.json()["data"]["is_read"] is True


@pytest.mark.django_db
def test_communication_scoped_to_own_records_not_whole_org(
    organization, user_factory, notification_factory, message_factory,
):
    user_a = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    user_b = user_factory(organization=organization, email="b@example.com", password="s3cret-pass!")
    notification_factory(recipient=user_a)
    notification_factory(recipient=user_b)
    message_factory(sender=user_a, recipient=user_b)

    activate_organization(organization.id)
    assert Notification.objects.filter(recipient=user_a).count() == 1
    assert Message.objects.filter(sender=user_a).count() == 1
