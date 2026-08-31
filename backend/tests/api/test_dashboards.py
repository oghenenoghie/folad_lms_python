import pytest


def _login(api_client, email, password):
    resp = api_client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    token = resp.json()["data"]["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


@pytest.mark.django_db
def test_student_dashboard_summary(
    api_client, organization, user_factory, school_factory, campus_factory, class_level_factory,
    class_arm_factory, academic_year_factory, student_factory, enrollment_factory, attendance_factory,
):
    school = school_factory(organization=organization)
    class_arm = class_arm_factory(class_level=class_level_factory(campus=campus_factory(school=school)))
    academic_year = academic_year_factory(school=school)
    student_user = user_factory(organization=organization, email="s@example.com", password="s3cret-pass!")
    student = student_factory(school=school, user=student_user)
    enrollment = enrollment_factory(student=student, class_arm=class_arm, academic_year=academic_year)
    attendance_factory(enrollment=enrollment, date="2025-09-01", status="present")
    attendance_factory(enrollment=enrollment, date="2025-09-02", status="absent")

    _login(api_client, "s@example.com", "s3cret-pass!")
    resp = api_client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["role"] == "student"
    assert data["attendance"]["present"] == 1
    assert data["attendance"]["absent"] == 1
    assert "outstanding_fees_minor" in data


@pytest.mark.django_db
def test_teacher_dashboard_summary(
    api_client, organization, user_factory, school_factory, campus_factory, class_level_factory,
    class_arm_factory, subject_factory, staff_factory, teacher_factory, class_subject_factory,
    academic_year_factory, term_factory, student_factory, enrollment_factory, assignment_factory,
    assignment_submission_factory,
):
    school = school_factory(organization=organization)
    class_arm = class_arm_factory(class_level=class_level_factory(campus=campus_factory(school=school)))
    subject = subject_factory(school=school)
    teacher_user = user_factory(organization=organization, email="t@example.com", password="s3cret-pass!")
    staff = staff_factory(school=school, user=teacher_user)
    teacher = teacher_factory(staff=staff)
    class_subject = class_subject_factory(class_arm=class_arm, subject=subject, teacher=teacher)
    academic_year = academic_year_factory(school=school)
    term = term_factory(academic_year=academic_year)
    student = student_factory(school=school)
    enrollment_factory(student=student, class_arm=class_arm, academic_year=academic_year)
    assignment = assignment_factory(class_subject=class_subject, term=term)
    assignment_submission_factory(assignment=assignment, student=student, status="submitted")

    _login(api_client, "t@example.com", "s3cret-pass!")
    resp = api_client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["role"] == "teacher"
    assert data["class_subjects_count"] == 1
    assert data["students_taught_count"] == 1
    assert data["pending_grading_count"] == 1


@pytest.mark.django_db
def test_guardian_dashboard_summary(
    api_client, organization, user_factory, school_factory, student_factory, guardian_factory,
    guardian_student_factory,
):
    school = school_factory(organization=organization)
    guardian_user = user_factory(organization=organization, email="g@example.com", password="s3cret-pass!")
    guardian = guardian_factory(organization=organization, user=guardian_user)
    child = student_factory(school=school)
    guardian_student_factory(guardian=guardian, student=child)

    _login(api_client, "g@example.com", "s3cret-pass!")
    resp = api_client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["role"] == "guardian"
    assert len(data["children"]) == 1
    assert data["children"][0]["name"] == f"{child.first_name} {child.last_name}"


@pytest.mark.django_db
def test_admin_dashboard_summary_falls_back_when_no_profile_linked(
    api_client, organization, user_factory, school_factory, student_factory,
):
    school_factory(organization=organization)
    user_factory(organization=organization, email="admin@example.com", password="s3cret-pass!")
    _login(api_client, "admin@example.com", "s3cret-pass!")

    resp = api_client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["role"] == "admin"
    assert "total_students" in data
    assert "net_receivable_minor" in data


@pytest.mark.django_db
def test_admin_dashboard_summary_includes_real_finance_and_attendance_metrics(
    api_client, organization, user_factory, school_factory, term_factory, academic_year_factory,
    student_factory, invoice_factory, payment_factory, campus_factory, class_level_factory,
    class_arm_factory, enrollment_factory, attendance_factory,
):
    import datetime

    school = school_factory(organization=organization)
    term = term_factory(academic_year=academic_year_factory(school=school))
    student = student_factory(school=school)

    paid_today = invoice_factory(
        student=student, term=term, invoice_number="INV-T1", total_minor=100_000, status="issued"
    )
    payment_factory(invoice=paid_today, reference="PAY-T1", amount_minor=100_000)
    overdue = invoice_factory(
        student=student, term=term, invoice_number="INV-OD1", total_minor=50_000,
        status="issued", due_date=datetime.date.today() - datetime.timedelta(days=3),
    )

    class_arm = class_arm_factory(class_level=class_level_factory(campus=campus_factory(school=school)))
    academic_year = term.academic_year
    enrollment = enrollment_factory(student=student, class_arm=class_arm, academic_year=academic_year)
    attendance_factory(enrollment=enrollment, date=datetime.date.today(), status="present")

    user_factory(organization=organization, email="admin2@example.com", password="s3cret-pass!")
    _login(api_client, "admin2@example.com", "s3cret-pass!")

    resp = api_client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["today_collection_minor"] == 100_000
    assert data["total_receivables_minor"] == overdue.total_minor
    assert data["attendance_today_pct"] == 100.0
    assert data["new_admissions_this_month"] == 1
    assert len(data["revenue_series"]) == 30
    assert len(data["top_defaulters"]) == 1
    assert data["top_defaulters"][0]["student_public_id"] == str(student.public_id)
    assert data["attendance_heatmap"]["classes"][0]["values"][-1] == 100
