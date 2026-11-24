import pytest
from django.db import ProgrammingError, connection, transaction

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.attendance.models import Attendance, AttendanceAudit
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


def _enroll(organization, school_factory, campus_factory, class_level_factory, class_arm_factory,
            academic_year_factory, student_factory, enrollment_factory):
    school = school_factory(organization=organization)
    class_arm = class_arm_factory(class_level=class_level_factory(campus=campus_factory(school=school)))
    academic_year = academic_year_factory(school=school)
    student = student_factory(school=school)
    return enrollment_factory(student=student, class_arm=class_arm, academic_year=academic_year)


@pytest.mark.django_db
def test_attendance_create_list_retrieve_update_delete(
    api_client, organization, user_factory, school_factory, campus_factory, class_level_factory,
    class_arm_factory, academic_year_factory, student_factory, enrollment_factory,
):
    enrollment = _enroll(organization, school_factory, campus_factory, class_level_factory,
                          class_arm_factory, academic_year_factory, student_factory, enrollment_factory)
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "attendance.view", "attendance.create", "attendance.update", "attendance.delete")
    _login(api_client, "a@example.com", "s3cret-pass!")

    create = api_client.post(
        "/api/v1/attendance",
        {"enrollment": str(enrollment.public_id), "date": "2025-09-01", "status": "present"},
        format="json",
    )
    assert create.status_code == 201
    body = create.json()
    assert "organization" not in body["data"]
    public_id = body["data"]["public_id"]

    listed = api_client.get(f"/api/v1/attendance?enrollment_id={enrollment.public_id}")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1

    retrieved = api_client.get(f"/api/v1/attendance/{public_id}")
    assert retrieved.status_code == 200
    assert retrieved.json()["data"]["status"] == "present"

    updated = api_client.patch(f"/api/v1/attendance/{public_id}", {"status": "absent"}, format="json")
    assert updated.status_code == 200
    assert updated.json()["data"]["status"] == "absent"

    deleted = api_client.delete(f"/api/v1/attendance/{public_id}")
    assert deleted.status_code == 200

    gone = api_client.get(f"/api/v1/attendance/{public_id}")
    assert gone.status_code == 404


@pytest.mark.django_db
def test_attendance_duplicate_enrollment_date_returns_conflict(
    api_client, organization, user_factory, school_factory, campus_factory, class_level_factory,
    class_arm_factory, academic_year_factory, student_factory, enrollment_factory,
):
    enrollment = _enroll(organization, school_factory, campus_factory, class_level_factory,
                          class_arm_factory, academic_year_factory, student_factory, enrollment_factory)
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "attendance.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    payload = {"enrollment": str(enrollment.public_id), "date": "2025-09-01", "status": "present"}
    first = api_client.post("/api/v1/attendance", payload, format="json")
    assert first.status_code == 201

    duplicate = api_client.post("/api/v1/attendance", {**payload, "status": "absent"}, format="json")
    assert duplicate.status_code == 409
    assert duplicate.json()["success"] is False


@pytest.mark.django_db
def test_attendance_app_layer_tenant_isolation(
    organization, other_organization, school_factory, campus_factory, class_level_factory,
    class_arm_factory, academic_year_factory, student_factory, enrollment_factory, attendance_factory,
):
    enrollment_a = _enroll(organization, school_factory, campus_factory, class_level_factory,
                            class_arm_factory, academic_year_factory, student_factory, enrollment_factory)
    enrollment_b = _enroll(other_organization, school_factory, campus_factory, class_level_factory,
                            class_arm_factory, academic_year_factory, student_factory, enrollment_factory)
    attendance_factory(enrollment=enrollment_a)
    attendance_factory(enrollment=enrollment_b)

    activate_organization(organization.id)
    visible = Attendance.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id


@pytest.mark.django_db
def test_marking_attendance_writes_audit_trail(
    api_client, organization, user_factory, school_factory, campus_factory, class_level_factory,
    class_arm_factory, academic_year_factory, student_factory, enrollment_factory,
):
    enrollment = _enroll(organization, school_factory, campus_factory, class_level_factory,
                          class_arm_factory, academic_year_factory, student_factory, enrollment_factory)
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "attendance.view", "attendance.create", "attendance.update")
    _login(api_client, "a@example.com", "s3cret-pass!")

    create = api_client.post(
        "/api/v1/attendance",
        {"enrollment": str(enrollment.public_id), "date": "2025-09-01", "status": "present"},
        format="json",
    )
    public_id = create.json()["data"]["public_id"]

    audit_after_create = api_client.get(f"/api/v1/attendance-audit?attendance_id={public_id}")
    assert audit_after_create.status_code == 200
    entries = audit_after_create.json()["data"]["results"]
    assert len(entries) == 1
    assert entries[0]["previous_status"] == ""
    assert entries[0]["new_status"] == "present"

    api_client.patch(f"/api/v1/attendance/{public_id}", {"status": "late"}, format="json")

    audit_after_update = api_client.get(f"/api/v1/attendance-audit?attendance_id={public_id}")
    entries = audit_after_update.json()["data"]["results"]
    assert len(entries) == 2
    latest = next(e for e in entries if e["new_status"] == "late")
    assert latest["previous_status"] == "present"


@pytest.mark.skipif(connection.vendor != "postgresql", reason="append-only trigger is Postgres-only")
@pytest.mark.django_db
def test_attendance_audit_is_append_only_at_db_level(
    organization, school_factory, campus_factory, class_level_factory, class_arm_factory,
    academic_year_factory, student_factory, enrollment_factory, attendance_factory,
):
    enrollment = _enroll(organization, school_factory, campus_factory, class_level_factory,
                          class_arm_factory, academic_year_factory, student_factory, enrollment_factory)
    attendance = attendance_factory(enrollment=enrollment)
    activate_organization(organization.id)
    audit = AttendanceAudit.all_tenants.create(
        organization=organization, attendance=attendance, previous_status="", new_status="present"
    )

    with pytest.raises(ProgrammingError, match="append-only"):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE attendance_attendance_audit SET new_status = %s WHERE id = %s",
                    ["absent", audit.id],
                )

    with pytest.raises(ProgrammingError, match="append-only"):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM attendance_attendance_audit WHERE id = %s", [audit.id])
