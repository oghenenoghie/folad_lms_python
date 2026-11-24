import pytest


def _login(api_client, email, password):
    resp = api_client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    token = resp.json()["data"]["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


@pytest.fixture
def two_students_setup(
    organization, user_factory, school_factory, campus_factory, class_level_factory, class_arm_factory,
    academic_year_factory, term_factory, subject_factory, staff_factory, teacher_factory,
    class_subject_factory, student_factory, enrollment_factory, assignment_factory, attendance_factory,
    assessment_factory, result_factory, invoice_factory, guardian_factory, guardian_student_factory,
):
    """One class arm, two enrolled students (own_student and other_student),
    each with their own attendance/assignment-adjacent/result/invoice data,
    plus a guardian linked only to own_student — the fixture every test
    below uses to prove data never crosses from one student/guardian to
    another.
    """
    school = school_factory(organization=organization)
    campus = campus_factory(school=school)
    class_level = class_level_factory(campus=campus)
    class_arm = class_arm_factory(class_level=class_level)
    academic_year = academic_year_factory(school=school)
    term = term_factory(academic_year=academic_year)
    subject = subject_factory(school=school)
    staff = staff_factory(school=school)
    teacher = teacher_factory(staff=staff)
    class_subject = class_subject_factory(class_arm=class_arm, subject=subject, teacher=teacher)

    own_user = user_factory(organization=organization, email="own@example.com", password="s3cret-pass!")
    own_student = student_factory(
        school=school, user=own_user, admission_number="A001", first_name="Own", last_name="Student"
    )
    own_enrollment = enrollment_factory(student=own_student, class_arm=class_arm, academic_year=academic_year)

    other_user = user_factory(organization=organization, email="other@example.com", password="s3cret-pass!")
    other_student = student_factory(
        school=school, user=other_user, admission_number="A002", first_name="Other", last_name="Student"
    )
    other_enrollment = enrollment_factory(
        student=other_student, class_arm=class_arm, academic_year=academic_year
    )

    assignment = assignment_factory(class_subject=class_subject, term=term)

    attendance_factory(enrollment=own_enrollment, date="2025-09-01", status="present")
    attendance_factory(enrollment=other_enrollment, date="2025-09-01", status="absent")

    assessment = assessment_factory(class_subject=class_subject, term=term)
    result_factory(assessment=assessment, student=own_student, score="70.00", status="published")
    result_factory(assessment=assessment, student=other_student, score="90.00", status="published")

    invoice_factory(student=own_student, term=term, invoice_number="INV-OWN")
    invoice_factory(student=other_student, term=term, invoice_number="INV-OTHER")

    guardian_user = user_factory(
        organization=organization, email="guardian@example.com", password="s3cret-pass!"
    )
    guardian = guardian_factory(organization=organization, user=guardian_user)
    guardian_student_factory(guardian=guardian, student=own_student)

    return {
        "own_student": own_student,
        "other_student": other_student,
        "assignment": assignment,
    }


@pytest.mark.django_db
class TestStudentSelfService:
    def test_student_sees_only_own_attendance(self, api_client, two_students_setup):
        _login(api_client, "own@example.com", "s3cret-pass!")
        resp = api_client.get("/api/v1/dashboard/my-attendance")
        assert resp.status_code == 200
        results = resp.json()["data"]["results"]
        assert len(results) == 1
        assert results[0]["status"] == "present"

    def test_student_sees_only_own_results(self, api_client, two_students_setup):
        _login(api_client, "own@example.com", "s3cret-pass!")
        resp = api_client.get("/api/v1/dashboard/my-results")
        assert resp.status_code == 200
        results = resp.json()["data"]["results"]
        assert len(results) == 1
        assert results[0]["score"] == "70.00"

    def test_student_sees_only_own_invoices(self, api_client, two_students_setup):
        _login(api_client, "own@example.com", "s3cret-pass!")
        resp = api_client.get("/api/v1/dashboard/my-invoices")
        assert resp.status_code == 200
        results = resp.json()["data"]["results"]
        assert len(results) == 1
        assert results[0]["invoice_number"] == "INV-OWN"

    def test_student_sees_own_class_assignments(self, api_client, two_students_setup):
        _login(api_client, "own@example.com", "s3cret-pass!")
        resp = api_client.get("/api/v1/dashboard/my-assignments")
        assert resp.status_code == 200
        results = resp.json()["data"]["results"]
        assert len(results) == 1

    def test_unpublished_result_is_never_returned(
        self, api_client, two_students_setup, assessment_factory, result_factory,
    ):
        from apps.examinations.models import Result

        own_student = two_students_setup["own_student"]
        published_assessment = Result.all_tenants.get(student=own_student, status="published").assessment
        draft_assessment = assessment_factory(
            class_subject=published_assessment.class_subject, term=published_assessment.term,
            name="Not Yet Published",
        )
        result_factory(assessment=draft_assessment, student=own_student, score="99.00", status="entered")

        _login(api_client, "own@example.com", "s3cret-pass!")
        resp = api_client.get("/api/v1/dashboard/my-results")
        data = resp.json()["data"]["results"]
        assert len(data) == 1
        assert all(r["status"] == "published" for r in data)


@pytest.mark.django_db
class TestGuardianSelfService:
    def test_guardian_lists_own_children(self, api_client, two_students_setup):
        _login(api_client, "guardian@example.com", "s3cret-pass!")
        resp = api_client.get("/api/v1/dashboard/my-children")
        assert resp.status_code == 200
        results = resp.json()["data"]["results"]
        assert len(results) == 1
        assert results[0]["admission_number"] == "A001"

    def test_guardian_sees_own_childs_attendance_with_student_id(self, api_client, two_students_setup):
        own_student = two_students_setup["own_student"]
        _login(api_client, "guardian@example.com", "s3cret-pass!")
        resp = api_client.get(f"/api/v1/dashboard/my-attendance?student_id={own_student.public_id}")
        assert resp.status_code == 200
        results = resp.json()["data"]["results"]
        assert len(results) == 1
        assert results[0]["status"] == "present"

    def test_guardian_cannot_see_a_non_linked_students_data(self, api_client, two_students_setup):
        other_student = two_students_setup["other_student"]
        _login(api_client, "guardian@example.com", "s3cret-pass!")
        resp = api_client.get(f"/api/v1/dashboard/my-attendance?student_id={other_student.public_id}")
        assert resp.status_code == 404

    def test_guardian_without_student_id_is_rejected(self, api_client, two_students_setup):
        _login(api_client, "guardian@example.com", "s3cret-pass!")
        resp = api_client.get("/api/v1/dashboard/my-invoices")
        assert resp.status_code == 400


@pytest.mark.django_db
def test_admin_without_a_linked_profile_is_rejected(
    api_client, organization, user_factory, school_factory,
):
    school_factory(organization=organization)
    user_factory(organization=organization, email="admin@example.com", password="s3cret-pass!")
    _login(api_client, "admin@example.com", "s3cret-pass!")

    resp = api_client.get("/api/v1/dashboard/my-invoices")
    assert resp.status_code == 403
