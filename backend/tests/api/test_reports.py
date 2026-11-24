import pytest

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.reports.models import ReportRequest
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
def test_student_list_report_csv(
    api_client, organization, user_factory, school_factory, student_factory,
):
    school = school_factory(organization=organization)
    student_factory(school=school, admission_number="A100", first_name="Amaka", last_name="Obi")

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "reports.view", "reports.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    created = api_client.post(
        "/api/v1/reports",
        {"school": str(school.public_id), "report_type": "student_list", "format": "csv"},
        format="json",
    )
    assert created.status_code == 201
    report_public_id = created.json()["data"]["public_id"]

    # CELERY_TASK_ALWAYS_EAGER runs the task synchronously above.
    retrieved = api_client.get(f"/api/v1/reports/{report_public_id}")
    body = retrieved.json()["data"]
    assert body["status"] == "ready"
    assert body["file_name"] == "student_list.csv"

    download = api_client.get(f"/api/v1/reports/{report_public_id}/download")
    assert download.status_code == 200
    assert download.json()["data"]["url"]


@pytest.mark.django_db
def test_fee_collection_report_xlsx(
    api_client, organization, user_factory, school_factory, academic_year_factory, term_factory,
    student_factory, invoice_factory,
):
    school = school_factory(organization=organization)
    term = term_factory(academic_year=academic_year_factory(school=school))
    student = student_factory(school=school)
    invoice_factory(student=student, term=term, invoice_number="INV-500", total_minor=100_000, status="issued")

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "reports.view", "reports.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    created = api_client.post(
        "/api/v1/reports",
        {
            "school": str(school.public_id), "report_type": "fee_collection", "format": "xlsx",
            "parameters": {"term_id": str(term.public_id)},
        },
        format="json",
    )
    assert created.status_code == 201
    report_public_id = created.json()["data"]["public_id"]

    retrieved = api_client.get(f"/api/v1/reports/{report_public_id}")
    body = retrieved.json()["data"]
    assert body["status"] == "ready"
    assert body["file_name"] == "fee_collection.xlsx"


@pytest.mark.django_db
def test_results_summary_report_pdf(
    api_client, organization, user_factory, school_factory, campus_factory, class_level_factory,
    class_arm_factory, subject_factory, staff_factory, teacher_factory, class_subject_factory,
    academic_year_factory, term_factory, student_factory, assessment_factory, result_factory,
):
    school = school_factory(organization=organization)
    class_arm = class_arm_factory(class_level=class_level_factory(campus=campus_factory(school=school)))
    subject = subject_factory(school=school)
    teacher = teacher_factory(staff=staff_factory(school=school))
    class_subject = class_subject_factory(class_arm=class_arm, subject=subject, teacher=teacher)
    term = term_factory(academic_year=academic_year_factory(school=school))
    student = student_factory(school=school)
    assessment = assessment_factory(class_subject=class_subject, term=term)
    result_factory(assessment=assessment, student=student, status="published")

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "reports.view", "reports.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    created = api_client.post(
        "/api/v1/reports",
        {"school": str(school.public_id), "report_type": "results_summary", "format": "pdf"},
        format="json",
    )
    assert created.status_code == 201
    report_public_id = created.json()["data"]["public_id"]

    retrieved = api_client.get(f"/api/v1/reports/{report_public_id}")
    body = retrieved.json()["data"]
    assert body["status"] == "ready"
    assert body["content_type"] == "application/pdf"


@pytest.mark.django_db
def test_reports_app_layer_tenant_isolation(
    organization, other_organization, school_factory,
):
    school_a = school_factory(organization=organization)
    school_b = school_factory(organization=other_organization)
    activate_organization(organization.id)
    from apps.reports.services import report_service

    report_service.request_report(
        school=school_a, report_type="student_list", format="csv", parameters={}, actor=None
    )
    activate_organization(other_organization.id)
    report_service.request_report(
        school=school_b, report_type="student_list", format="csv", parameters={}, actor=None
    )

    activate_organization(organization.id)
    visible = ReportRequest.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id
