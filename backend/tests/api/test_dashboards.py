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
def test_teacher_dashboard_summary_includes_todays_schedule_and_pending_submissions(
    api_client, organization, user_factory, school_factory, campus_factory, class_level_factory,
    class_arm_factory, subject_factory, staff_factory, teacher_factory, class_subject_factory,
    academic_year_factory, term_factory, student_factory, enrollment_factory, assignment_factory,
    assignment_submission_factory, period_factory, timetable_slot_factory,
):
    from django.utils import timezone

    school = school_factory(organization=organization)
    class_arm = class_arm_factory(class_level=class_level_factory(campus=campus_factory(school=school)))
    subject = subject_factory(school=school)
    teacher_user = user_factory(organization=organization, email="t2@example.com", password="s3cret-pass!")
    staff = staff_factory(school=school, user=teacher_user, employee_number="EMP-002")
    teacher = teacher_factory(staff=staff)
    class_subject = class_subject_factory(class_arm=class_arm, subject=subject, teacher=teacher)
    academic_year = academic_year_factory(school=school)
    term = term_factory(academic_year=academic_year)
    student = student_factory(school=school, admission_number="A100", first_name="Pending", last_name="Grader")
    enrollment_factory(student=student, class_arm=class_arm, academic_year=academic_year)
    assignment = assignment_factory(class_subject=class_subject, term=term, title="Essay 1")
    assignment_submission_factory(assignment=assignment, student=student, status="submitted")

    today_weekday = timezone.now().strftime("%A").lower()
    period = period_factory(school=school, name="Period 1")
    timetable_slot_factory(class_subject=class_subject, period=period, day_of_week=today_weekday)

    _login(api_client, "t2@example.com", "s3cret-pass!")
    resp = api_client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["todays_periods_count"] == 1
    assert data["todays_periods"][0]["subject"] == subject.name
    assert data["todays_periods"][0]["period"] == "Period 1"
    assert len(data["pending_submissions"]) == 1
    assert data["pending_submissions"][0]["assignment"] == "Essay 1"
    assert data["pending_submissions"][0]["student"] == "Pending Grader"


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


@pytest.mark.django_db
def test_admin_dashboard_summary_is_cached_for_the_ttl(
    api_client, organization, user_factory, school_factory, student_factory,
):
    school = school_factory(organization=organization)
    user_factory(organization=organization, email="admin4@example.com", password="s3cret-pass!")
    _login(api_client, "admin4@example.com", "s3cret-pass!")

    first = api_client.get("/api/v1/dashboard/summary").json()["data"]
    assert first["total_students"] == 0

    # A student created after the first request shouldn't show up until the
    # cache entry expires — proves _cached_admin_summary is actually caching
    # rather than recomputing every request.
    student_factory(school=school)
    second = api_client.get("/api/v1/dashboard/summary").json()["data"]
    assert second["total_students"] == 0


@pytest.mark.django_db
def test_admin_dashboard_summary_cache_is_scoped_per_organization(
    api_client, organization, other_organization, user_factory, school_factory, student_factory,
):
    user_factory(organization=organization, email="admin-a@example.com", password="s3cret-pass!")
    user_factory(organization=other_organization, email="admin-b@example.com", password="s3cret-pass!")
    student_factory(school=school_factory(organization=organization))

    _login(api_client, "admin-a@example.com", "s3cret-pass!")
    data_a = api_client.get("/api/v1/dashboard/summary").json()["data"]
    assert data_a["total_students"] == 1

    _login(api_client, "admin-b@example.com", "s3cret-pass!")
    data_b = api_client.get("/api/v1/dashboard/summary").json()["data"]
    assert data_b["total_students"] == 0


@pytest.mark.django_db
def test_admin_dashboard_summary_includes_eduportal_widgets(
    api_client, organization, user_factory, school_factory, student_factory, staff_factory,
    teacher_factory, achievement_factory, message_factory, announcement_factory,
    notification_factory,
):
    school = school_factory(organization=organization)
    student_factory(school=school, admission_number="EW1", gender="male")
    student_factory(school=school, admission_number="EW2", gender="female")
    achievement_factory(student=student_factory(school=school, admission_number="EW3"), title="Top scorer")
    staff = staff_factory(school=school, employee_number="EWS1")
    teacher_factory(staff=staff)

    admin = user_factory(organization=organization, email="admin3@example.com", password="s3cret-pass!")
    sender = user_factory(organization=organization, email="sender3@example.com")
    message_factory(sender=sender, recipient=admin, subject="Hello")
    announcement_factory(school=school, title="Sports day")
    notification_factory(recipient=admin, title="New payment received")

    _login(api_client, "admin3@example.com", "s3cret-pass!")

    resp = api_client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["total_teachers"] == 1
    assert data["total_achievements"] == 1
    assert data["gender_breakdown"]["male"] == 1
    assert data["gender_breakdown"]["female"] == 1
    assert len(data["enrollment_series_monthly"]) > 0
    assert len(data["enrollment_series_weekly"]) == 8
    assert len(data["recent_messages"]) == 1
    assert data["unread_message_count"] == 1
    assert len(data["notices"]) == 1
    assert data["notices"][0]["title"] == "Sports day"
    assert len(data["recent_activity"]) == 1
    assert data["recent_activity"][0]["title"] == "New payment received"
    assert "weeks" in data["calendar"]
    assert "recent_logins" in data
    assert len(data["weekly_attendance"]["days"]) == 5
