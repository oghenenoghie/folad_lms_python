import pytest
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def _clear_cache():
    """Redis isn't reset between test runs the way the Postgres test DB is
    (which is recreated fresh, resetting PK sequences to 1 each run) — a
    stale permissions cache entry (accounts.cache_keys: `perms:<user_id>:
    <org_id>`) from an earlier run can collide with a freshly created user
    that happens to get the same low ID, silently granting permissions that
    were never actually assigned in this run."""
    from django.core.cache import cache

    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def organization(db):
    from apps.tenancy.models import Organization

    return Organization.objects.create(name="Test Org")


@pytest.fixture
def other_organization(db):
    from apps.tenancy.models import Organization

    return Organization.objects.create(name="Other Org")


@pytest.fixture
def user_factory(db):
    from apps.accounts.models import User

    def make(*, organization, email="user@example.com", password="correct horse battery staple", **extra):
        return User.objects.create_user(
            email=email, password=password, first_name="Test", last_name="User",
            organization=organization, **extra,
        )

    return make


@pytest.fixture
def school_factory(db):
    from apps.schools.models import School
    from apps.tenancy.context import activate_organization

    def make(*, organization, name="Test School", code="TS", **extra):
        activate_organization(organization.id)
        return School.all_tenants.create(organization=organization, name=name, code=code, **extra)

    return make


@pytest.fixture
def campus_factory(db):
    from apps.schools.models import Campus
    from apps.tenancy.context import activate_organization

    def make(*, school, name="Main Campus", code="MC", **extra):
        activate_organization(school.organization_id)
        return Campus.all_tenants.create(
            organization=school.organization, school=school, name=name, code=code, **extra
        )

    return make


@pytest.fixture
def academic_year_factory(db):
    from apps.schools.models import AcademicYear
    from apps.tenancy.context import activate_organization

    def make(*, school, name="2025/2026", start_date="2025-09-01", end_date="2026-07-31", **extra):
        activate_organization(school.organization_id)
        return AcademicYear.all_tenants.create(
            organization=school.organization,
            school=school,
            name=name,
            start_date=start_date,
            end_date=end_date,
            **extra,
        )

    return make


@pytest.fixture
def term_factory(db):
    from apps.schools.models import Term
    from apps.tenancy.context import activate_organization

    def make(*, academic_year, name="First Term", sequence=1, start_date="2025-09-01", end_date="2025-12-15", **extra):
        activate_organization(academic_year.organization_id)
        return Term.all_tenants.create(
            organization=academic_year.organization,
            academic_year=academic_year,
            name=name,
            sequence=sequence,
            start_date=start_date,
            end_date=end_date,
            **extra,
        )

    return make


@pytest.fixture
def department_factory(db):
    from apps.schools.models import Department
    from apps.tenancy.context import activate_organization

    def make(*, school, name="Sciences", code="SCI", **extra):
        activate_organization(school.organization_id)
        return Department.all_tenants.create(
            organization=school.organization, school=school, name=name, code=code, **extra
        )

    return make


@pytest.fixture
def student_factory(db):
    from apps.students.models import Student
    from apps.tenancy.context import activate_organization

    def make(
        *,
        school,
        admission_number="A001",
        first_name="Alex",
        last_name="Doe",
        date_of_birth="2012-01-01",
        **extra,
    ):
        activate_organization(school.organization_id)
        return Student.all_tenants.create(
            organization=school.organization,
            school=school,
            admission_number=admission_number,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            **extra,
        )

    return make


@pytest.fixture
def guardian_student_factory(db):
    from apps.parents.models import GuardianStudent
    from apps.tenancy.context import activate_organization

    def make(*, student, guardian, relationship_type="guardian", **extra):
        activate_organization(student.organization_id)
        return GuardianStudent.all_tenants.create(
            organization=student.organization,
            student=student,
            guardian=guardian,
            relationship_type=relationship_type,
            **extra,
        )

    return make


@pytest.fixture
def staff_factory(db):
    from apps.staff.models import Staff
    from apps.tenancy.context import activate_organization

    def make(
        *, school, employee_number="EMP-001", first_name="Sam", last_name="Smith",
        position="Teacher", date_joined="2020-01-01", **extra,
    ):
        activate_organization(school.organization_id)
        return Staff.all_tenants.create(
            organization=school.organization,
            school=school,
            employee_number=employee_number,
            first_name=first_name,
            last_name=last_name,
            position=position,
            date_joined=date_joined,
            **extra,
        )

    return make


@pytest.fixture
def teacher_factory(db):
    from apps.staff.models import Teacher
    from apps.tenancy.context import activate_organization

    def make(*, staff, **extra):
        activate_organization(staff.organization_id)
        return Teacher.all_tenants.create(organization=staff.organization, staff=staff, **extra)

    return make


@pytest.fixture
def guardian_factory(db):
    from apps.parents.models import Guardian
    from apps.tenancy.context import activate_organization

    def make(*, organization, first_name="Jane", last_name="Doe", **extra):
        activate_organization(organization.id)
        return Guardian.all_tenants.create(
            organization=organization, first_name=first_name, last_name=last_name, **extra
        )

    return make


@pytest.fixture
def class_level_factory(db):
    from apps.academics.models import ClassLevel
    from apps.tenancy.context import activate_organization

    def make(*, campus, name="Grade 1", sequence=1, **extra):
        activate_organization(campus.organization_id)
        return ClassLevel.all_tenants.create(
            organization=campus.organization, campus=campus, name=name, sequence=sequence, **extra
        )

    return make


@pytest.fixture
def class_arm_factory(db):
    from apps.academics.models import ClassArm
    from apps.tenancy.context import activate_organization

    def make(*, class_level, name="A", **extra):
        activate_organization(class_level.organization_id)
        return ClassArm.all_tenants.create(
            organization=class_level.organization, class_level=class_level, name=name, **extra
        )

    return make


@pytest.fixture
def subject_factory(db):
    from apps.academics.models import Subject
    from apps.tenancy.context import activate_organization

    def make(*, school, name="Mathematics", code="MTH", **extra):
        activate_organization(school.organization_id)
        return Subject.all_tenants.create(
            organization=school.organization, school=school, name=name, code=code, **extra
        )

    return make


@pytest.fixture
def class_subject_factory(db):
    from apps.academics.models import ClassSubject
    from apps.tenancy.context import activate_organization

    def make(*, class_arm, subject, teacher, **extra):
        activate_organization(class_arm.organization_id)
        return ClassSubject.all_tenants.create(
            organization=class_arm.organization,
            class_arm=class_arm,
            subject=subject,
            teacher=teacher,
            **extra,
        )

    return make


@pytest.fixture
def enrollment_factory(db):
    from apps.academics.models import Enrollment
    from apps.tenancy.context import activate_organization

    def make(*, student, class_arm, academic_year, effective_from="2025-09-01", **extra):
        activate_organization(student.organization_id)
        return Enrollment.all_tenants.create(
            organization=student.organization,
            student=student,
            class_arm=class_arm,
            academic_year=academic_year,
            effective_from=effective_from,
            **extra,
        )

    return make


@pytest.fixture
def attendance_factory(db):
    from apps.attendance.models import Attendance
    from apps.tenancy.context import activate_organization

    def make(*, enrollment, date="2025-09-01", status="present", **extra):
        activate_organization(enrollment.organization_id)
        return Attendance.all_tenants.create(
            organization=enrollment.organization,
            enrollment=enrollment,
            date=date,
            status=status,
            **extra,
        )

    return make


@pytest.fixture
def room_factory(db):
    from apps.timetable.models import Room
    from apps.tenancy.context import activate_organization

    def make(*, campus, name="Room 1", **extra):
        activate_organization(campus.organization_id)
        return Room.all_tenants.create(organization=campus.organization, campus=campus, name=name, **extra)

    return make


@pytest.fixture
def period_factory(db):
    from apps.timetable.models import Period
    from apps.tenancy.context import activate_organization

    def make(*, school, name="Period 1", sequence=1, start_time="08:00", end_time="08:40", **extra):
        activate_organization(school.organization_id)
        return Period.all_tenants.create(
            organization=school.organization,
            school=school,
            name=name,
            sequence=sequence,
            start_time=start_time,
            end_time=end_time,
            **extra,
        )

    return make


@pytest.fixture
def timetable_slot_factory(db):
    from apps.timetable.models import TimetableSlot
    from apps.tenancy.context import activate_organization

    def make(*, class_subject, period, day_of_week="monday", room=None, **extra):
        activate_organization(class_subject.organization_id)
        return TimetableSlot.all_tenants.create(
            organization=class_subject.organization,
            class_subject=class_subject,
            class_arm=class_subject.class_arm,
            teacher=class_subject.teacher,
            room=room,
            day_of_week=day_of_week,
            period=period,
            **extra,
        )

    return make


@pytest.fixture
def grading_scheme_factory(db):
    from apps.examinations.models import GradingScheme
    from apps.tenancy.context import activate_organization

    def make(*, school, name="Standard", is_default=True, **extra):
        activate_organization(school.organization_id)
        return GradingScheme.all_tenants.create(
            organization=school.organization, school=school, name=name, is_default=is_default, **extra
        )

    return make


@pytest.fixture
def grade_band_factory(db):
    from apps.examinations.models import GradeBand
    from apps.tenancy.context import activate_organization

    def make(*, grading_scheme, grade="A", min_score="70.00", max_score="100.00", remark="Excellent", **extra):
        activate_organization(grading_scheme.organization_id)
        return GradeBand.all_tenants.create(
            organization=grading_scheme.organization,
            grading_scheme=grading_scheme,
            grade=grade,
            min_score=min_score,
            max_score=max_score,
            remark=remark,
            **extra,
        )

    return make


@pytest.fixture
def exam_factory(db):
    from apps.examinations.models import Exam
    from apps.tenancy.context import activate_organization

    def make(*, term, name="First Term Exam", start_date="2025-12-01", end_date="2025-12-10", **extra):
        activate_organization(term.organization_id)
        return Exam.all_tenants.create(
            organization=term.organization,
            school=term.academic_year.school,
            academic_year=term.academic_year,
            term=term,
            name=name,
            start_date=start_date,
            end_date=end_date,
            **extra,
        )

    return make


@pytest.fixture
def exam_schedule_factory(db):
    from apps.examinations.models import ExamSchedule
    from apps.tenancy.context import activate_organization

    def make(
        *, exam, class_subject, date="2025-12-02", start_time="09:00", end_time="11:00", **extra
    ):
        activate_organization(exam.organization_id)
        return ExamSchedule.all_tenants.create(
            organization=exam.organization,
            exam=exam,
            class_subject=class_subject,
            date=date,
            start_time=start_time,
            end_time=end_time,
            **extra,
        )

    return make


@pytest.fixture
def invigilator_factory(db):
    from apps.examinations.models import Invigilator
    from apps.tenancy.context import activate_organization

    def make(*, exam_schedule, teacher, **extra):
        activate_organization(exam_schedule.organization_id)
        return Invigilator.all_tenants.create(
            organization=exam_schedule.organization,
            exam_schedule=exam_schedule,
            teacher=teacher,
            **extra,
        )

    return make


@pytest.fixture
def assessment_factory(db):
    from apps.examinations.models import Assessment
    from apps.tenancy.context import activate_organization

    def make(
        *,
        class_subject,
        term,
        name="Mid-term Test",
        assessment_type="test",
        weight="30.00",
        max_score="100.00",
        **extra,
    ):
        activate_organization(class_subject.organization_id)
        return Assessment.all_tenants.create(
            organization=class_subject.organization,
            class_subject=class_subject,
            term=term,
            name=name,
            assessment_type=assessment_type,
            weight=weight,
            max_score=max_score,
            **extra,
        )

    return make


@pytest.fixture
def result_factory(db):
    from apps.examinations.models import Result
    from apps.tenancy.context import activate_organization

    def make(*, assessment, student, score="80.00", **extra):
        activate_organization(assessment.organization_id)
        return Result.all_tenants.create(
            organization=assessment.organization,
            assessment=assessment,
            student=student,
            score=score,
            **extra,
        )

    return make


@pytest.fixture
def report_card_factory(db):
    from apps.examinations.models import ReportCard
    from apps.tenancy.context import activate_organization

    def make(*, student, term, **extra):
        activate_organization(student.organization_id)
        return ReportCard.all_tenants.create(
            organization=student.organization,
            student=student,
            academic_year=term.academic_year,
            term=term,
            **extra,
        )

    return make
