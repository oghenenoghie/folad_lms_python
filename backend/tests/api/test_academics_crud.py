import pytest

from apps.academics.models import ClassArm, ClassLevel, ClassSubject, Enrollment, Subject
from apps.accounts.models import Permission, Role, RolePermission, UserRole
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
def test_class_level_create_list_retrieve_update_delete(
    api_client, organization, user_factory, school_factory, campus_factory
):
    campus = campus_factory(school=school_factory(organization=organization))
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "class_levels.view", "class_levels.create", "class_levels.update", "class_levels.delete")
    _login(api_client, "a@example.com", "s3cret-pass!")

    create = api_client.post(
        "/api/v1/class-levels",
        {"campus": str(campus.public_id), "name": "Grade 1", "sequence": 1},
        format="json",
    )
    assert create.status_code == 201
    body = create.json()
    assert "organization" not in body["data"]
    public_id = body["data"]["public_id"]

    listed = api_client.get(f"/api/v1/class-levels?campus_id={campus.public_id}")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1

    retrieved = api_client.get(f"/api/v1/class-levels/{public_id}")
    assert retrieved.status_code == 200
    assert retrieved.json()["data"]["name"] == "Grade 1"

    updated = api_client.patch(f"/api/v1/class-levels/{public_id}", {"sequence": 2}, format="json")
    assert updated.status_code == 200
    assert updated.json()["data"]["sequence"] == 2

    deleted = api_client.delete(f"/api/v1/class-levels/{public_id}")
    assert deleted.status_code == 200

    gone = api_client.get(f"/api/v1/class-levels/{public_id}")
    assert gone.status_code == 404


@pytest.mark.django_db
def test_class_level_duplicate_name_returns_conflict(
    api_client, organization, user_factory, school_factory, campus_factory
):
    campus = campus_factory(school=school_factory(organization=organization))
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "class_levels.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    payload = {"campus": str(campus.public_id), "name": "Grade 1", "sequence": 1}
    first = api_client.post("/api/v1/class-levels", payload, format="json")
    assert first.status_code == 201

    duplicate = api_client.post("/api/v1/class-levels", {**payload, "sequence": 2}, format="json")
    assert duplicate.status_code == 409
    assert duplicate.json()["success"] is False


@pytest.mark.django_db
def test_class_level_app_layer_tenant_isolation(
    organization, other_organization, school_factory, campus_factory, class_level_factory
):
    class_level_factory(campus=campus_factory(school=school_factory(organization=organization)))
    class_level_factory(campus=campus_factory(school=school_factory(organization=other_organization)))

    activate_organization(organization.id)
    visible = ClassLevel.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id


@pytest.mark.django_db
def test_class_arm_create_and_list(
    api_client, organization, user_factory, school_factory, campus_factory, class_level_factory
):
    class_level = class_level_factory(campus=campus_factory(school=school_factory(organization=organization)))
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "class_arms.view", "class_arms.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    create = api_client.post(
        "/api/v1/class-arms", {"class_level": str(class_level.public_id), "name": "A"}, format="json"
    )
    assert create.status_code == 201

    listed = api_client.get(f"/api/v1/class-arms?class_level_id={class_level.public_id}")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1


@pytest.mark.django_db
def test_class_arm_app_layer_tenant_isolation(
    organization, other_organization, school_factory, campus_factory, class_level_factory, class_arm_factory
):
    class_arm_factory(
        class_level=class_level_factory(campus=campus_factory(school=school_factory(organization=organization)))
    )
    class_arm_factory(
        class_level=class_level_factory(
            campus=campus_factory(school=school_factory(organization=other_organization))
        )
    )

    activate_organization(organization.id)
    visible = ClassArm.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id


@pytest.mark.django_db
def test_subject_create_and_list(api_client, organization, user_factory, school_factory):
    school = school_factory(organization=organization)
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "subjects.view", "subjects.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    create = api_client.post(
        "/api/v1/subjects",
        {"school": str(school.public_id), "name": "Mathematics", "code": "MTH"},
        format="json",
    )
    assert create.status_code == 201

    listed = api_client.get(f"/api/v1/subjects?school_id={school.public_id}")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1


@pytest.mark.django_db
def test_subject_app_layer_tenant_isolation(
    organization, other_organization, school_factory, subject_factory
):
    subject_factory(school=school_factory(organization=organization))
    subject_factory(school=school_factory(organization=other_organization))

    activate_organization(organization.id)
    visible = Subject.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id


@pytest.mark.django_db
def test_class_subject_create_and_duplicate_conflict(
    api_client,
    organization,
    user_factory,
    school_factory,
    campus_factory,
    class_level_factory,
    class_arm_factory,
    subject_factory,
    staff_factory,
    teacher_factory,
):
    school = school_factory(organization=organization)
    class_arm = class_arm_factory(
        class_level=class_level_factory(campus=campus_factory(school=school))
    )
    subject = subject_factory(school=school)
    teacher = teacher_factory(staff=staff_factory(school=school))
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "class_subjects.view", "class_subjects.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    payload = {
        "class_arm": str(class_arm.public_id),
        "subject": str(subject.public_id),
        "teacher": str(teacher.public_id),
    }
    create = api_client.post("/api/v1/class-subjects", payload, format="json")
    assert create.status_code == 201

    listed = api_client.get(f"/api/v1/class-subjects?class_arm_id={class_arm.public_id}")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1

    duplicate = api_client.post("/api/v1/class-subjects", payload, format="json")
    assert duplicate.status_code == 409


@pytest.mark.django_db
def test_class_subject_app_layer_tenant_isolation(
    organization,
    other_organization,
    school_factory,
    campus_factory,
    class_level_factory,
    class_arm_factory,
    subject_factory,
    staff_factory,
    teacher_factory,
    class_subject_factory,
):
    school_a = school_factory(organization=organization)
    school_b = school_factory(organization=other_organization)
    class_subject_factory(
        class_arm=class_arm_factory(class_level=class_level_factory(campus=campus_factory(school=school_a))),
        subject=subject_factory(school=school_a),
        teacher=teacher_factory(staff=staff_factory(school=school_a)),
    )
    class_subject_factory(
        class_arm=class_arm_factory(class_level=class_level_factory(campus=campus_factory(school=school_b))),
        subject=subject_factory(school=school_b),
        teacher=teacher_factory(staff=staff_factory(school=school_b)),
    )

    activate_organization(organization.id)
    visible = ClassSubject.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id


@pytest.mark.django_db
def test_enrollment_create_list_retrieve_update_delete(
    api_client,
    organization,
    user_factory,
    school_factory,
    campus_factory,
    class_level_factory,
    class_arm_factory,
    academic_year_factory,
    student_factory,
):
    school = school_factory(organization=organization)
    class_arm = class_arm_factory(class_level=class_level_factory(campus=campus_factory(school=school)))
    academic_year = academic_year_factory(school=school)
    student = student_factory(school=school)
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "enrollments.view", "enrollments.create", "enrollments.update", "enrollments.delete")
    _login(api_client, "a@example.com", "s3cret-pass!")

    create = api_client.post(
        "/api/v1/enrollments",
        {
            "student": str(student.public_id),
            "class_arm": str(class_arm.public_id),
            "academic_year": str(academic_year.public_id),
            "effective_from": "2025-09-01",
        },
        format="json",
    )
    assert create.status_code == 201
    body = create.json()
    assert body["data"]["status"] == "active"
    public_id = body["data"]["public_id"]

    listed = api_client.get(f"/api/v1/enrollments?student_id={student.public_id}")
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] == 1

    updated = api_client.patch(f"/api/v1/enrollments/{public_id}", {"status": "withdrawn"}, format="json")
    assert updated.status_code == 200
    assert updated.json()["data"]["status"] == "withdrawn"

    deleted = api_client.delete(f"/api/v1/enrollments/{public_id}")
    assert deleted.status_code == 200

    gone = api_client.get(f"/api/v1/enrollments/{public_id}")
    assert gone.status_code == 404


@pytest.mark.django_db
def test_enrollment_duplicate_student_year_returns_conflict(
    api_client,
    organization,
    user_factory,
    school_factory,
    campus_factory,
    class_level_factory,
    class_arm_factory,
    academic_year_factory,
    student_factory,
):
    school = school_factory(organization=organization)
    class_level = class_level_factory(campus=campus_factory(school=school))
    class_arm_a = class_arm_factory(class_level=class_level, name="A")
    class_arm_b = class_arm_factory(class_level=class_level, name="B")
    academic_year = academic_year_factory(school=school)
    student = student_factory(school=school)
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "enrollments.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    first = api_client.post(
        "/api/v1/enrollments",
        {
            "student": str(student.public_id),
            "class_arm": str(class_arm_a.public_id),
            "academic_year": str(academic_year.public_id),
            "effective_from": "2025-09-01",
        },
        format="json",
    )
    assert first.status_code == 201

    # Same student, same academic year, a *different* class arm — still a
    # conflict: the M5 exit criterion is one enrollment per student per
    # year, not per (student, class_arm).
    duplicate = api_client.post(
        "/api/v1/enrollments",
        {
            "student": str(student.public_id),
            "class_arm": str(class_arm_b.public_id),
            "academic_year": str(academic_year.public_id),
            "effective_from": "2025-09-02",
        },
        format="json",
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["success"] is False


@pytest.mark.django_db
def test_enrollment_permission_denied_without_role(api_client, organization, user_factory):
    user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _login(api_client, "a@example.com", "s3cret-pass!")

    resp = api_client.get("/api/v1/enrollments")

    assert resp.status_code == 403


@pytest.mark.django_db
def test_enrollment_cross_tenant_isolation(
    api_client,
    organization,
    other_organization,
    user_factory,
    school_factory,
    campus_factory,
    class_level_factory,
    class_arm_factory,
    academic_year_factory,
    student_factory,
    enrollment_factory,
):
    school_a = school_factory(organization=organization)
    school_b = school_factory(organization=other_organization)
    enrollment_factory(
        student=student_factory(school=school_a),
        class_arm=class_arm_factory(class_level=class_level_factory(campus=campus_factory(school=school_a))),
        academic_year=academic_year_factory(school=school_a),
    )
    other_enrollment = enrollment_factory(
        student=student_factory(school=school_b),
        class_arm=class_arm_factory(class_level=class_level_factory(campus=campus_factory(school=school_b))),
        academic_year=academic_year_factory(school=school_b),
    )

    user_b = user_factory(organization=other_organization, email="b@example.com", password="s3cret-pass!")
    _grant(user_b, "enrollments.view")
    _login(api_client, "b@example.com", "s3cret-pass!")

    listed = api_client.get("/api/v1/enrollments")
    assert listed.status_code == 200
    results = listed.json()["data"]["results"]
    assert len(results) == 1
    assert results[0]["public_id"] == str(other_enrollment.public_id)


@pytest.mark.django_db
def test_enrollment_app_layer_tenant_isolation(
    organization,
    other_organization,
    school_factory,
    campus_factory,
    class_level_factory,
    class_arm_factory,
    academic_year_factory,
    student_factory,
    enrollment_factory,
):
    school_a = school_factory(organization=organization)
    school_b = school_factory(organization=other_organization)
    enrollment_factory(
        student=student_factory(school=school_a),
        class_arm=class_arm_factory(class_level=class_level_factory(campus=campus_factory(school=school_a))),
        academic_year=academic_year_factory(school=school_a),
    )
    enrollment_factory(
        student=student_factory(school=school_b),
        class_arm=class_arm_factory(class_level=class_level_factory(campus=campus_factory(school=school_b))),
        academic_year=academic_year_factory(school=school_b),
    )

    activate_organization(organization.id)
    visible = Enrollment.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id
