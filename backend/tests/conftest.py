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
def achievement_factory(db):
    from apps.students.models import Achievement
    from apps.tenancy.context import activate_organization

    def make(*, student, title="Science Fair Winner", awarded_on="2026-01-15", **extra):
        activate_organization(student.organization_id)
        return Achievement.all_tenants.create(
            organization=student.organization,
            school=student.school,
            student=student,
            title=title,
            awarded_on=awarded_on,
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
    import secrets

    from apps.report_cards.models import ReportCard
    from apps.tenancy.context import activate_organization

    def make(*, student, term, class_arm, **extra):
        activate_organization(student.organization_id)
        extra.setdefault("report_card_number", f"RC-TEST-{secrets.token_hex(4)}")
        extra.setdefault("verification_code", secrets.token_urlsafe(16))
        return ReportCard.all_tenants.create(
            organization=student.organization,
            student=student,
            academic_year=term.academic_year,
            term=term,
            class_level=class_arm.class_level,
            class_arm=class_arm,
            **extra,
        )

    return make


@pytest.fixture
def report_card_fixture_set(
    organization, school_factory, campus_factory, class_level_factory, class_arm_factory,
    subject_factory, staff_factory, teacher_factory, class_subject_factory,
    academic_year_factory, term_factory, student_factory, enrollment_factory,
):
    """One student, one subject, one class/term — the minimal scaffolding
    every apps.report_cards test (crud/pdf/verify) needs before it can
    generate a report card. Shared here rather than duplicated per test
    module since all three exercise the same generate_report_card() path.
    """
    school = school_factory(organization=organization)
    class_arm = class_arm_factory(class_level=class_level_factory(campus=campus_factory(school=school)))
    subject = subject_factory(school=school, name="Mathematics", code="MTH")
    teacher = teacher_factory(staff=staff_factory(school=school))
    class_subject = class_subject_factory(class_arm=class_arm, subject=subject, teacher=teacher)
    academic_year = academic_year_factory(school=school)
    term = term_factory(academic_year=academic_year)
    student = student_factory(school=school)
    enrollment = enrollment_factory(student=student, class_arm=class_arm, academic_year=academic_year)
    return {
        "school": school,
        "class_arm": class_arm,
        "subject": subject,
        "class_subject": class_subject,
        "academic_year": academic_year,
        "term": term,
        "student": student,
        "enrollment": enrollment,
    }


@pytest.fixture
def report_card_weighting_factory(db):
    from apps.report_cards.models import ReportCardWeighting
    from apps.tenancy.context import activate_organization

    def make(*, school, ca_weight="30.00", cbt_weight="30.00", exam_weight="40.00", **extra):
        activate_organization(school.organization_id)
        return ReportCardWeighting.all_tenants.create(
            organization=school.organization,
            school=school,
            ca_weight=ca_weight,
            cbt_weight=cbt_weight,
            exam_weight=exam_weight,
            **extra,
        )

    return make


@pytest.fixture
def report_card_bulk_export_factory(db):
    from apps.report_cards.models import ReportCardBulkExport
    from apps.tenancy.context import activate_organization

    def make(*, term, class_arm=None, actor=None, **extra):
        activate_organization(term.organization_id)
        return ReportCardBulkExport.objects.create(
            organization=term.organization,
            term=term,
            class_arm=class_arm,
            created_by=actor,
            updated_by=actor,
            **extra,
        )

    return make


@pytest.fixture
def question_factory(db):
    from apps.examinations.models import Question
    from apps.tenancy.context import activate_organization

    def make(*, assessment, question_type="multiple_choice", text="What is 2+2?", marks="10.00", sequence=1, **extra):
        activate_organization(assessment.organization_id)
        return Question.all_tenants.create(
            organization=assessment.organization,
            assessment=assessment,
            question_type=question_type,
            text=text,
            marks=marks,
            sequence=sequence,
            **extra,
        )

    return make


@pytest.fixture
def question_option_factory(db):
    from apps.examinations.models import QuestionOption
    from apps.tenancy.context import activate_organization

    def make(*, question, text="Option", is_correct=False, sequence=1, **extra):
        activate_organization(question.organization_id)
        return QuestionOption.all_tenants.create(
            organization=question.organization,
            question=question,
            text=text,
            is_correct=is_correct,
            sequence=sequence,
            **extra,
        )

    return make


@pytest.fixture
def student_answer_factory(db):
    from django.utils import timezone

    from apps.examinations.models import StudentAnswer
    from apps.tenancy.context import activate_organization

    def make(*, question, student, submitted_at=None, **extra):
        activate_organization(question.organization_id)
        return StudentAnswer.all_tenants.create(
            organization=question.organization,
            question=question,
            student=student,
            submitted_at=submitted_at or timezone.now(),
            **extra,
        )

    return make


@pytest.fixture
def fee_structure_factory(db):
    from apps.finance.models import FeeStructure
    from apps.tenancy.context import activate_organization

    def make(*, term, name="Term Fees", **extra):
        activate_organization(term.organization_id)
        return FeeStructure.all_tenants.create(
            organization=term.organization,
            school=term.academic_year.school,
            academic_year=term.academic_year,
            term=term,
            name=name,
            **extra,
        )

    return make


@pytest.fixture
def fee_item_factory(db):
    from apps.finance.models import FeeItem
    from apps.tenancy.context import activate_organization

    def make(*, fee_structure, name="Tuition", amount_minor=500_000, **extra):
        activate_organization(fee_structure.organization_id)
        return FeeItem.all_tenants.create(
            organization=fee_structure.organization,
            fee_structure=fee_structure,
            name=name,
            amount_minor=amount_minor,
            currency_code=fee_structure.organization.currency_code,
            **extra,
        )

    return make


@pytest.fixture
def discount_factory(db):
    from apps.finance.models import Discount
    from apps.tenancy.context import activate_organization

    def make(*, school, name="Sibling Discount", discount_type="percentage", **extra):
        activate_organization(school.organization_id)
        if discount_type == "percentage":
            extra.setdefault("percentage", "10.00")
        else:
            extra.setdefault("fixed_amount_minor", 10_000)
        return Discount.all_tenants.create(
            organization=school.organization,
            school=school,
            name=name,
            discount_type=discount_type,
            **extra,
        )

    return make


@pytest.fixture
def scholarship_factory(db):
    from apps.finance.models import Scholarship
    from apps.tenancy.context import activate_organization

    def make(*, student, discount, academic_year, **extra):
        activate_organization(student.organization_id)
        return Scholarship.all_tenants.create(
            organization=student.organization,
            school=student.school,
            student=student,
            discount=discount,
            academic_year=academic_year,
            **extra,
        )

    return make


@pytest.fixture
def invoice_factory(db):
    from apps.finance.models import Invoice
    from apps.tenancy.context import activate_organization

    def make(*, student, term, invoice_number="INV-0001", **extra):
        activate_organization(student.organization_id)
        return Invoice.all_tenants.create(
            organization=student.organization,
            school=term.academic_year.school,
            student=student,
            academic_year=term.academic_year,
            term=term,
            invoice_number=invoice_number,
            currency_code=student.organization.currency_code,
            **extra,
        )

    return make


@pytest.fixture
def invoice_line_factory(db):
    from apps.finance.models import InvoiceLine
    from apps.tenancy.context import activate_organization

    def make(*, invoice, description="Tuition", quantity=1, unit_amount_minor=500_000, **extra):
        activate_organization(invoice.organization_id)
        amount_minor = extra.pop("amount_minor", quantity * unit_amount_minor)
        return InvoiceLine.all_tenants.create(
            organization=invoice.organization,
            invoice=invoice,
            description=description,
            quantity=quantity,
            unit_amount_minor=unit_amount_minor,
            amount_minor=amount_minor,
            **extra,
        )

    return make


@pytest.fixture
def payment_factory(db):
    from django.utils import timezone

    from apps.finance.models import Payment
    from apps.tenancy.context import activate_organization

    def make(*, invoice, reference="PAY-0001", amount_minor=500_000, method="cash", **extra):
        activate_organization(invoice.organization_id)
        extra.setdefault("paid_at", timezone.now())
        return Payment.all_tenants.create(
            organization=invoice.organization,
            school=invoice.school,
            invoice=invoice,
            reference=reference,
            amount_minor=amount_minor,
            currency_code=invoice.currency_code,
            method=method,
            **extra,
        )

    return make


@pytest.fixture
def receipt_factory(db):
    from apps.finance.models import Receipt
    from apps.tenancy.context import activate_organization

    def make(*, payment, receipt_number=None, **extra):
        activate_organization(payment.organization_id)
        return Receipt.all_tenants.create(
            organization=payment.organization,
            school=payment.school,
            payment=payment,
            receipt_number=receipt_number or f"RCPT-{payment.reference}",
            **extra,
        )

    return make


@pytest.fixture
def library_book_factory(db):
    from apps.library.models import LibraryBook
    from apps.tenancy.context import activate_organization

    def make(*, school, title="Learning Django", **extra):
        activate_organization(school.organization_id)
        return LibraryBook.all_tenants.create(
            organization=school.organization, school=school, title=title, **extra
        )

    return make


@pytest.fixture
def library_copy_factory(db):
    from apps.library.models import LibraryCopy
    from apps.tenancy.context import activate_organization

    def make(*, book, copy_number="C-001", **extra):
        activate_organization(book.organization_id)
        return LibraryCopy.all_tenants.create(
            organization=book.organization, book=book, copy_number=copy_number, **extra
        )

    return make


@pytest.fixture
def library_member_factory(db):
    from apps.library.models import LibraryMember
    from apps.tenancy.context import activate_organization

    def make(*, school, student=None, staff=None, membership_number="M-001", **extra):
        activate_organization(school.organization_id)
        member_type = "student" if student else "staff"
        return LibraryMember.all_tenants.create(
            organization=school.organization,
            school=school,
            member_type=member_type,
            student=student,
            staff=staff,
            membership_number=membership_number,
            **extra,
        )

    return make


@pytest.fixture
def library_loan_factory(db):
    from apps.library.models import LibraryLoan
    from apps.tenancy.context import activate_organization

    def make(*, copy, member, borrowed_date="2025-09-01", due_date="2025-09-15", **extra):
        activate_organization(copy.organization_id)
        return LibraryLoan.all_tenants.create(
            organization=copy.organization,
            copy=copy,
            member=member,
            borrowed_date=borrowed_date,
            due_date=due_date,
            **extra,
        )

    return make


@pytest.fixture
def inventory_item_factory(db):
    from apps.inventory.models import InventoryItem
    from apps.tenancy.context import activate_organization

    def make(*, school, name="Whiteboard Markers", sku="SKU-001", **extra):
        activate_organization(school.organization_id)
        return InventoryItem.all_tenants.create(
            organization=school.organization, school=school, name=name, sku=sku, **extra
        )

    return make


@pytest.fixture
def supplier_factory(db):
    from apps.inventory.models import Supplier
    from apps.tenancy.context import activate_organization

    def make(*, school, name="Acme Supplies", **extra):
        activate_organization(school.organization_id)
        return Supplier.all_tenants.create(
            organization=school.organization, school=school, name=name, **extra
        )

    return make


@pytest.fixture
def purchase_order_factory(db):
    from apps.inventory.models import PurchaseOrder
    from apps.tenancy.context import activate_organization

    def make(*, item, supplier, order_number="PO-001", quantity_ordered=10, unit_cost_minor=500, **extra):
        activate_organization(item.organization_id)
        return PurchaseOrder.all_tenants.create(
            organization=item.organization,
            school=item.school,
            supplier=supplier,
            item=item,
            order_number=order_number,
            quantity_ordered=quantity_ordered,
            unit_cost_minor=unit_cost_minor,
            currency_code=item.organization.currency_code,
            **extra,
        )

    return make


@pytest.fixture
def vehicle_factory(db):
    from apps.transport.models import Vehicle
    from apps.tenancy.context import activate_organization

    def make(*, school, registration_number="ABC-123", capacity=20, **extra):
        activate_organization(school.organization_id)
        return Vehicle.all_tenants.create(
            organization=school.organization,
            school=school,
            registration_number=registration_number,
            capacity=capacity,
            **extra,
        )

    return make


@pytest.fixture
def transport_route_factory(db):
    from apps.transport.models import TransportRoute
    from apps.tenancy.context import activate_organization

    def make(*, school, name="North Route", **extra):
        activate_organization(school.organization_id)
        return TransportRoute.all_tenants.create(
            organization=school.organization, school=school, name=name, **extra
        )

    return make


@pytest.fixture
def route_stop_factory(db):
    from apps.transport.models import RouteStop
    from apps.tenancy.context import activate_organization

    def make(*, route, name="Main Gate", sequence=1, pickup_time="07:00", **extra):
        activate_organization(route.organization_id)
        return RouteStop.all_tenants.create(
            organization=route.organization,
            route=route,
            name=name,
            sequence=sequence,
            pickup_time=pickup_time,
            **extra,
        )

    return make


@pytest.fixture
def transport_assignment_factory(db):
    from apps.transport.models import TransportAssignment
    from apps.tenancy.context import activate_organization

    def make(*, student, vehicle, route, stop, academic_year, assigned_date="2025-09-01", **extra):
        activate_organization(student.organization_id)
        return TransportAssignment.all_tenants.create(
            organization=student.organization,
            student=student,
            vehicle=vehicle,
            route=route,
            stop=stop,
            academic_year=academic_year,
            assigned_date=assigned_date,
            **extra,
        )

    return make


@pytest.fixture
def hostel_factory(db):
    from apps.hostel.models import Hostel
    from apps.tenancy.context import activate_organization

    def make(*, school, name="North Hostel", hostel_type="mixed", **extra):
        activate_organization(school.organization_id)
        return Hostel.all_tenants.create(
            organization=school.organization, school=school, name=name, hostel_type=hostel_type, **extra
        )

    return make


@pytest.fixture
def hostel_building_factory(db):
    from apps.hostel.models import HostelBuilding
    from apps.tenancy.context import activate_organization

    def make(*, hostel, name="Block A", **extra):
        activate_organization(hostel.organization_id)
        return HostelBuilding.all_tenants.create(
            organization=hostel.organization, hostel=hostel, name=name, **extra
        )

    return make


@pytest.fixture
def hostel_room_factory(db):
    from apps.hostel.models import HostelRoom
    from apps.tenancy.context import activate_organization

    def make(*, building, room_number="101", capacity=4, **extra):
        activate_organization(building.organization_id)
        return HostelRoom.all_tenants.create(
            organization=building.organization,
            building=building,
            room_number=room_number,
            capacity=capacity,
            **extra,
        )

    return make


@pytest.fixture
def hostel_bed_factory(db):
    from apps.hostel.models import HostelBed
    from apps.tenancy.context import activate_organization

    def make(*, room, bed_number="A", **extra):
        activate_organization(room.organization_id)
        return HostelBed.all_tenants.create(
            organization=room.organization, room=room, bed_number=bed_number, **extra
        )

    return make


@pytest.fixture
def hostel_allocation_factory(db):
    from apps.hostel.models import HostelAllocation
    from apps.tenancy.context import activate_organization

    def make(*, student, bed, academic_year, allocated_date="2025-09-01", **extra):
        activate_organization(student.organization_id)
        return HostelAllocation.all_tenants.create(
            organization=student.organization,
            student=student,
            bed=bed,
            academic_year=academic_year,
            allocated_date=allocated_date,
            **extra,
        )

    return make


@pytest.fixture
def assignment_factory(db):
    from apps.assignments.models import Assignment
    from apps.tenancy.context import activate_organization

    def make(*, class_subject, term, title="Homework 1", due_date="2025-09-15", max_score="100.00", **extra):
        activate_organization(class_subject.organization_id)
        return Assignment.all_tenants.create(
            organization=class_subject.organization,
            class_subject=class_subject,
            term=term,
            title=title,
            due_date=due_date,
            max_score=max_score,
            **extra,
        )

    return make


@pytest.fixture
def assignment_submission_factory(db):
    from django.utils import timezone

    from apps.assignments.models import AssignmentSubmission
    from apps.tenancy.context import activate_organization

    def make(*, assignment, student, text_content="My answer", **extra):
        activate_organization(assignment.organization_id)
        extra.setdefault("submitted_at", timezone.now())
        return AssignmentSubmission.all_tenants.create(
            organization=assignment.organization,
            assignment=assignment,
            student=student,
            text_content=text_content,
            **extra,
        )

    return make


@pytest.fixture
def announcement_factory(db):
    from apps.communication.models import Announcement
    from apps.tenancy.context import activate_organization

    def make(*, school, title="Term begins", body="Welcome back!", **extra):
        activate_organization(school.organization_id)
        return Announcement.all_tenants.create(
            organization=school.organization, school=school, title=title, body=body, **extra
        )

    return make


@pytest.fixture
def notification_factory(db):
    from apps.communication.models import Notification
    from apps.tenancy.context import activate_organization

    def make(*, recipient, notification_type="system", title="Heads up", **extra):
        activate_organization(recipient.organization_id)
        return Notification.all_tenants.create(
            organization=recipient.organization,
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            **extra,
        )

    return make


@pytest.fixture
def message_factory(db):
    from apps.communication.models import Message
    from apps.tenancy.context import activate_organization

    def make(*, sender, recipient, subject="Hi", body="Hello there", **extra):
        activate_organization(sender.organization_id)
        return Message.all_tenants.create(
            organization=sender.organization,
            sender=sender,
            recipient=recipient,
            subject=subject,
            body=body,
            **extra,
        )

    return make


@pytest.fixture
def document_factory(db):
    from apps.documents.models import Document
    from apps.tenancy.context import activate_organization

    def make(
        *, school, student=None, staff=None, document_type="id_card", title="ID Card",
        storage_key="documents/test/key.pdf", file_name="id.pdf", content_type="application/pdf",
        size_bytes=1024, **extra,
    ):
        activate_organization(school.organization_id)
        owner_type = "student" if student else "staff"
        return Document.all_tenants.create(
            organization=school.organization,
            school=school,
            owner_type=owner_type,
            student=student,
            staff=staff,
            document_type=document_type,
            title=title,
            storage_key=storage_key,
            file_name=file_name,
            content_type=content_type,
            size_bytes=size_bytes,
            **extra,
        )

    return make
