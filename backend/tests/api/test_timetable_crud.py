import pytest

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.tenancy.context import activate_organization
from apps.timetable.models import Period, Room, TimetableSlot


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
def test_room_create_and_list(api_client, organization, user_factory, school_factory, campus_factory):
    campus = campus_factory(school=school_factory(organization=organization))
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "rooms.view", "rooms.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    create = api_client.post(
        "/api/v1/rooms", {"campus": str(campus.public_id), "name": "Lab 1", "capacity": 30}, format="json"
    )
    assert create.status_code == 201

    listed = api_client.get(f"/api/v1/rooms?campus_id={campus.public_id}")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1


@pytest.mark.django_db
def test_room_app_layer_tenant_isolation(
    organization, other_organization, school_factory, campus_factory, room_factory
):
    room_factory(campus=campus_factory(school=school_factory(organization=organization)))
    room_factory(campus=campus_factory(school=school_factory(organization=other_organization)))

    activate_organization(organization.id)
    visible = Room.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id


@pytest.mark.django_db
def test_period_create_and_duplicate_sequence_conflict(
    api_client, organization, user_factory, school_factory
):
    school = school_factory(organization=organization)
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "periods.view", "periods.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    payload = {
        "school": str(school.public_id),
        "name": "Period 1",
        "sequence": 1,
        "start_time": "08:00",
        "end_time": "08:40",
    }
    first = api_client.post("/api/v1/periods", payload, format="json")
    assert first.status_code == 201

    duplicate = api_client.post(
        "/api/v1/periods", {**payload, "name": "Period 1 Redux"}, format="json"
    )
    assert duplicate.status_code == 409


@pytest.mark.django_db
def test_period_app_layer_tenant_isolation(
    organization, other_organization, school_factory, period_factory
):
    period_factory(school=school_factory(organization=organization))
    period_factory(school=school_factory(organization=other_organization))

    activate_organization(organization.id)
    visible = Period.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id


def _class_subject(school_factory, campus_factory, class_level_factory, class_arm_factory,
                    subject_factory, staff_factory, teacher_factory, class_subject_factory,
                    *, organization, arm_name="A"):
    school = school_factory(organization=organization)
    class_level = class_level_factory(campus=campus_factory(school=school))
    class_arm = class_arm_factory(class_level=class_level, name=arm_name)
    subject = subject_factory(school=school)
    teacher = teacher_factory(staff=staff_factory(school=school))
    return class_subject_factory(class_arm=class_arm, subject=subject, teacher=teacher), school


@pytest.mark.django_db
def test_timetable_slot_create_and_list(
    api_client, organization, user_factory, school_factory, campus_factory, class_level_factory,
    class_arm_factory, subject_factory, staff_factory, teacher_factory, class_subject_factory,
    period_factory,
):
    class_subject, school = _class_subject(
        school_factory, campus_factory, class_level_factory, class_arm_factory, subject_factory,
        staff_factory, teacher_factory, class_subject_factory, organization=organization,
    )
    period = period_factory(school=school)
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "timetable_slots.view", "timetable_slots.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    create = api_client.post(
        "/api/v1/timetable-slots",
        {
            "class_subject": str(class_subject.public_id),
            "day_of_week": "monday",
            "period": str(period.public_id),
        },
        format="json",
    )
    assert create.status_code == 201
    body = create.json()
    # class_arm/teacher are read-only, server-derived from class_subject.
    assert body["data"]["class_arm"] == str(class_subject.class_arm.public_id)
    assert body["data"]["teacher"] == str(class_subject.teacher.public_id)

    listed = api_client.get(f"/api/v1/timetable-slots?class_arm_id={class_subject.class_arm.public_id}")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1


@pytest.mark.django_db
def test_timetable_slot_rejects_teacher_double_booking(
    api_client, organization, user_factory, school_factory, campus_factory, class_level_factory,
    class_arm_factory, subject_factory, staff_factory, teacher_factory, class_subject_factory,
    period_factory,
):
    school = school_factory(organization=organization)
    campus = campus_factory(school=school)
    class_level = class_level_factory(campus=campus)
    arm_a = class_arm_factory(class_level=class_level, name="A")
    arm_b = class_arm_factory(class_level=class_level, name="B")
    subject = subject_factory(school=school)
    # Same teacher, teaching two different arms — a real double-booking.
    teacher = teacher_factory(staff=staff_factory(school=school))
    cs_a = class_subject_factory(class_arm=arm_a, subject=subject, teacher=teacher)
    cs_b = class_subject_factory(class_arm=arm_b, subject=subject, teacher=teacher)
    period = period_factory(school=school)
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "timetable_slots.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    first = api_client.post(
        "/api/v1/timetable-slots",
        {"class_subject": str(cs_a.public_id), "day_of_week": "monday", "period": str(period.public_id)},
        format="json",
    )
    assert first.status_code == 201

    conflict = api_client.post(
        "/api/v1/timetable-slots",
        {"class_subject": str(cs_b.public_id), "day_of_week": "monday", "period": str(period.public_id)},
        format="json",
    )
    assert conflict.status_code == 409


@pytest.mark.django_db
def test_timetable_slot_rejects_room_double_booking(
    api_client, organization, user_factory, school_factory, campus_factory, class_level_factory,
    class_arm_factory, subject_factory, staff_factory, teacher_factory, class_subject_factory,
    period_factory, room_factory,
):
    school = school_factory(organization=organization)
    campus = campus_factory(school=school)
    class_level = class_level_factory(campus=campus)
    arm_a = class_arm_factory(class_level=class_level, name="A")
    arm_b = class_arm_factory(class_level=class_level, name="B")
    subject = subject_factory(school=school)
    cs_a = class_subject_factory(
        class_arm=arm_a, subject=subject, teacher=teacher_factory(staff=staff_factory(school=school, employee_number="T1"))
    )
    cs_b = class_subject_factory(
        class_arm=arm_b, subject=subject, teacher=teacher_factory(staff=staff_factory(school=school, employee_number="T2"))
    )
    period = period_factory(school=school)
    room = room_factory(campus=campus)
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "timetable_slots.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    first = api_client.post(
        "/api/v1/timetable-slots",
        {
            "class_subject": str(cs_a.public_id),
            "day_of_week": "monday",
            "period": str(period.public_id),
            "room": str(room.public_id),
        },
        format="json",
    )
    assert first.status_code == 201

    # Different teacher, different class arm — no conflict on either of
    # those, but the *same room* at the same day+period is still a
    # double-booking.
    conflict = api_client.post(
        "/api/v1/timetable-slots",
        {
            "class_subject": str(cs_b.public_id),
            "day_of_week": "monday",
            "period": str(period.public_id),
            "room": str(room.public_id),
        },
        format="json",
    )
    assert conflict.status_code == 409


@pytest.mark.django_db
def test_timetable_slot_allows_multiple_unassigned_rooms_same_slot(
    api_client, organization, user_factory, school_factory, campus_factory, class_level_factory,
    class_arm_factory, subject_factory, staff_factory, teacher_factory, class_subject_factory,
    period_factory,
):
    """Two slots with no room at all must not collide on the room
    constraint — it's conditional on room being set."""
    school = school_factory(organization=organization)
    campus = campus_factory(school=school)
    class_level = class_level_factory(campus=campus)
    arm_a = class_arm_factory(class_level=class_level, name="A")
    arm_b = class_arm_factory(class_level=class_level, name="B")
    subject = subject_factory(school=school)
    cs_a = class_subject_factory(
        class_arm=arm_a, subject=subject, teacher=teacher_factory(staff=staff_factory(school=school, employee_number="T1"))
    )
    cs_b = class_subject_factory(
        class_arm=arm_b, subject=subject, teacher=teacher_factory(staff=staff_factory(school=school, employee_number="T2"))
    )
    period = period_factory(school=school)
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "timetable_slots.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    first = api_client.post(
        "/api/v1/timetable-slots",
        {"class_subject": str(cs_a.public_id), "day_of_week": "monday", "period": str(period.public_id)},
        format="json",
    )
    assert first.status_code == 201

    second = api_client.post(
        "/api/v1/timetable-slots",
        {"class_subject": str(cs_b.public_id), "day_of_week": "monday", "period": str(period.public_id)},
        format="json",
    )
    assert second.status_code == 201


@pytest.mark.django_db
def test_timetable_slot_app_layer_tenant_isolation(
    organization, other_organization, school_factory, campus_factory, class_level_factory,
    class_arm_factory, subject_factory, staff_factory, teacher_factory, class_subject_factory,
    period_factory, timetable_slot_factory,
):
    cs_a, school_a = _class_subject(
        school_factory, campus_factory, class_level_factory, class_arm_factory, subject_factory,
        staff_factory, teacher_factory, class_subject_factory, organization=organization,
    )
    cs_b, school_b = _class_subject(
        school_factory, campus_factory, class_level_factory, class_arm_factory, subject_factory,
        staff_factory, teacher_factory, class_subject_factory, organization=other_organization,
    )
    timetable_slot_factory(class_subject=cs_a, period=period_factory(school=school_a))
    timetable_slot_factory(class_subject=cs_b, period=period_factory(school=school_b))

    activate_organization(organization.id)
    visible = TimetableSlot.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id
