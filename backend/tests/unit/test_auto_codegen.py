"""Every "code"-shaped identifier below is optional at the model level —
Model.save() fills it in when left blank (apps.core.codegen) — and an
explicitly given value is always respected instead. One test per model
proves the auto-generated case; two extra tests exercise the shared
codegen helpers' collision handling directly, since duplicating that
across every model's test would be pure repetition.
"""
import pytest


@pytest.mark.django_db
def test_subject_code_is_derived_from_name_when_blank(organization, school_factory, subject_factory):
    school = school_factory(organization=organization)
    subject = subject_factory(school=school, name="Mathematics", code="")
    assert subject.code == "MAT"


@pytest.mark.django_db
def test_school_code_is_derived_from_name_when_blank(organization, school_factory):
    school = school_factory(organization=organization, name="Higher Ground Academy", code="")
    assert school.code == "HIG"


@pytest.mark.django_db
def test_campus_code_is_derived_from_name_when_blank(organization, school_factory, campus_factory):
    school = school_factory(organization=organization)
    campus = campus_factory(school=school, name="North Wing", code="")
    assert campus.code == "NOR"


@pytest.mark.django_db
def test_department_code_is_derived_from_name_when_blank(organization, school_factory, department_factory):
    school = school_factory(organization=organization)
    department = department_factory(school=school, name="Sciences", code="")
    assert department.code == "SCI"


@pytest.mark.django_db
def test_student_admission_number_is_sequential_per_school_when_blank(
    organization, school_factory, student_factory,
):
    school = school_factory(organization=organization, code="HGA")
    first = student_factory(school=school, admission_number="")
    second = student_factory(school=school, admission_number="")
    assert first.admission_number == "HGA-0001"
    assert second.admission_number == "HGA-0002"


@pytest.mark.django_db
def test_staff_employee_number_is_sequential_per_school_when_blank(
    organization, school_factory, staff_factory,
):
    school = school_factory(organization=organization)
    first = staff_factory(school=school, employee_number="")
    second = staff_factory(school=school, employee_number="")
    assert first.employee_number == "EMP-0001"
    assert second.employee_number == "EMP-0002"


@pytest.mark.django_db
def test_invoice_number_is_sequential_per_school_when_blank(
    organization, school_factory, term_factory, academic_year_factory, student_factory, invoice_factory,
):
    school = school_factory(organization=organization)
    term = term_factory(academic_year=academic_year_factory(school=school))
    student = student_factory(school=school)
    invoice = invoice_factory(student=student, term=term, invoice_number="")
    assert invoice.invoice_number == "INV-0001"


@pytest.mark.django_db
def test_purchase_order_number_is_sequential_per_school_when_blank(
    organization, school_factory, inventory_item_factory, supplier_factory, purchase_order_factory,
):
    school = school_factory(organization=organization)
    item = inventory_item_factory(school=school)
    supplier = supplier_factory(school=school)
    order = purchase_order_factory(item=item, supplier=supplier, order_number="")
    assert order.order_number == "PO-0001"


@pytest.mark.django_db
def test_library_member_number_is_sequential_per_school_when_blank(
    organization, school_factory, student_factory, library_member_factory,
):
    school = school_factory(organization=organization)
    student = student_factory(school=school)
    member = library_member_factory(school=school, student=student, membership_number="")
    assert member.membership_number == "LIB-0001"


@pytest.mark.django_db
def test_library_copy_number_is_sequential_per_book_when_blank(
    organization, school_factory, library_book_factory, library_copy_factory,
):
    school = school_factory(organization=organization)
    book = library_book_factory(school=school)
    first = library_copy_factory(book=book, copy_number="")
    second = library_copy_factory(book=book, copy_number="")
    assert first.copy_number == "1"
    assert second.copy_number == "2"


@pytest.mark.django_db
def test_hostel_room_number_is_sequential_per_building_when_blank(
    organization, school_factory, hostel_factory, hostel_building_factory, hostel_room_factory,
):
    school = school_factory(organization=organization)
    building = hostel_building_factory(hostel=hostel_factory(school=school))
    first = hostel_room_factory(building=building, room_number="")
    second = hostel_room_factory(building=building, room_number="")
    assert first.room_number == "1"
    assert second.room_number == "2"


@pytest.mark.django_db
def test_hostel_bed_number_is_sequential_per_room_when_blank(
    organization, school_factory, hostel_factory, hostel_building_factory, hostel_room_factory,
    hostel_bed_factory,
):
    school = school_factory(organization=organization)
    building = hostel_building_factory(hostel=hostel_factory(school=school))
    room = hostel_room_factory(building=building)
    first = hostel_bed_factory(room=room, bed_number="")
    second = hostel_bed_factory(room=room, bed_number="")
    assert first.bed_number == "1"
    assert second.bed_number == "2"


@pytest.mark.django_db
def test_explicit_code_is_never_overridden(organization, school_factory, subject_factory):
    school = school_factory(organization=organization)
    subject = subject_factory(school=school, name="Mathematics", code="CUSTOM")
    assert subject.code == "CUSTOM"


@pytest.mark.django_db
def test_abbreviation_code_collision_appends_a_numeric_suffix(
    organization, school_factory, subject_factory,
):
    school = school_factory(organization=organization)
    subject_factory(school=school, name="Mathematics", code="")
    second = subject_factory(school=school, name="Materials Science", code="")
    assert second.code == "MAT2"
