import datetime

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.assignments.models import Assignment
from apps.tenancy.context import activate_organization

_PDF_BYTES = b"%PDF-1.4\n%mock pdf content for tests\n"


def _grant(user, *codes):
    role = Role.objects.create(name=f"ROLE_{user.pk}_{'_'.join(codes)}"[:100], label="Test Role")
    for code in codes:
        RolePermission.objects.create(role=role, permission=Permission.objects.get(code=code))
    UserRole.objects.create(user=user, role=role)


def _login(api_client, email, password):
    resp = api_client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    token = resp.json()["data"]["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def _class_subject(
    organization, school_factory, campus_factory, class_level_factory, class_arm_factory,
    subject_factory, staff_factory, teacher_factory, class_subject_factory,
):
    school = school_factory(organization=organization)
    class_arm = class_arm_factory(class_level=class_level_factory(campus=campus_factory(school=school)))
    subject = subject_factory(school=school)
    teacher = teacher_factory(staff=staff_factory(school=school))
    return class_subject_factory(class_arm=class_arm, subject=subject, teacher=teacher)


@pytest.fixture
def assignment_fixture_set(
    organization, school_factory, campus_factory, class_level_factory, class_arm_factory,
    subject_factory, staff_factory, teacher_factory, class_subject_factory,
    academic_year_factory, term_factory, student_factory,
):
    class_subject = _class_subject(
        organization, school_factory, campus_factory, class_level_factory, class_arm_factory,
        subject_factory, staff_factory, teacher_factory, class_subject_factory,
    )
    school = class_subject.class_arm.class_level.campus.school
    term = term_factory(academic_year=academic_year_factory(school=school))
    student = student_factory(school=school)
    return {"class_subject": class_subject, "term": term, "student": student}


@pytest.mark.django_db
def test_text_submission_and_grading(
    api_client, organization, user_factory, assignment_fixture_set,
):
    class_subject = assignment_fixture_set["class_subject"]
    term = assignment_fixture_set["term"]
    student = assignment_fixture_set["student"]

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(
        user, "assignments.view", "assignments.create",
        "assignment_submissions.view", "assignment_submissions.create", "assignment_submissions.update",
    )
    _login(api_client, "a@example.com", "s3cret-pass!")

    due_date = (timezone.now().date() + datetime.timedelta(days=7)).isoformat()
    created = api_client.post(
        "/api/v1/assignments",
        {
            "class_subject": str(class_subject.public_id), "term": str(term.public_id),
            "title": "Essay 1", "due_date": due_date, "max_score": "100.00",
        },
        format="json",
    )
    assert created.status_code == 201
    assignment_public_id = created.json()["data"]["public_id"]

    submitted = api_client.post(
        "/api/v1/assignment-submissions",
        {
            "assignment": assignment_public_id, "student": str(student.public_id),
            "text_content": "My essay content",
        },
        format="json",
    )
    assert submitted.status_code == 201
    submission_public_id = submitted.json()["data"]["public_id"]
    assert submitted.json()["data"]["status"] == "submitted"

    duplicate = api_client.post(
        "/api/v1/assignment-submissions",
        {
            "assignment": assignment_public_id, "student": str(student.public_id),
            "text_content": "A second attempt",
        },
        format="json",
    )
    assert duplicate.status_code == 409

    graded = api_client.post(
        f"/api/v1/assignment-submissions/{submission_public_id}/grade",
        {"score": "85.00", "feedback": "Good work"},
        format="json",
    )
    assert graded.status_code == 200
    assert graded.json()["data"]["status"] == "graded"
    assert graded.json()["data"]["score"] == "85.00"


@pytest.mark.django_db
def test_file_submission_and_download(
    api_client, organization, user_factory, assignment_fixture_set, assignment_factory,
):
    class_subject = assignment_fixture_set["class_subject"]
    term = assignment_fixture_set["term"]
    student = assignment_fixture_set["student"]
    assignment = assignment_factory(class_subject=class_subject, term=term)

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "assignment_submissions.view", "assignment_submissions.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    upload = api_client.post(
        "/api/v1/assignment-submissions/upload",
        {
            "assignment": str(assignment.public_id), "student": str(student.public_id),
            "file": SimpleUploadedFile("essay.pdf", _PDF_BYTES, content_type="application/pdf"),
        },
        format="multipart",
    )
    assert upload.status_code == 201, upload.json()
    submission_public_id = upload.json()["data"]["public_id"]
    assert upload.json()["data"]["file_name"] == "essay.pdf"

    download = api_client.get(f"/api/v1/assignment-submissions/{submission_public_id}/download")
    assert download.status_code == 200
    assert download.json()["data"]["url"]


@pytest.mark.django_db
def test_assignments_app_layer_tenant_isolation(
    organization, other_organization, school_factory, campus_factory, class_level_factory,
    class_arm_factory, subject_factory, staff_factory, teacher_factory, class_subject_factory,
    academic_year_factory, term_factory, assignment_factory,
):
    cs_a = _class_subject(
        organization, school_factory, campus_factory, class_level_factory, class_arm_factory,
        subject_factory, staff_factory, teacher_factory, class_subject_factory,
    )
    cs_b = _class_subject(
        other_organization, school_factory, campus_factory, class_level_factory, class_arm_factory,
        subject_factory, staff_factory, teacher_factory, class_subject_factory,
    )
    term_a = term_factory(academic_year=academic_year_factory(school=cs_a.class_arm.class_level.campus.school))
    term_b = term_factory(academic_year=academic_year_factory(school=cs_b.class_arm.class_level.campus.school))
    assignment_factory(class_subject=cs_a, term=term_a)
    assignment_factory(class_subject=cs_b, term=term_b)

    activate_organization(organization.id)
    visible = Assignment.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id
