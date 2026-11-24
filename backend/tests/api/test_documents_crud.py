import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.documents.models import Document
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


@pytest.mark.django_db
def test_upload_and_download_document(
    api_client, organization, user_factory, school_factory, student_factory,
):
    school = school_factory(organization=organization)
    student = student_factory(school=school)

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "documents.view", "documents.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    upload = api_client.post(
        "/api/v1/documents/upload",
        {
            "school": str(school.public_id), "document_type": "birth_certificate", "title": "Birth Certificate",
            "student": str(student.public_id),
            "file": SimpleUploadedFile("cert.pdf", _PDF_BYTES, content_type="application/pdf"),
        },
        format="multipart",
    )
    assert upload.status_code == 201, upload.json()
    document_public_id = upload.json()["data"]["public_id"]
    assert upload.json()["data"]["owner_type"] == "student"

    download = api_client.get(f"/api/v1/documents/{document_public_id}/download")
    assert download.status_code == 200
    assert download.json()["data"]["url"]

    listed = api_client.get(f"/api/v1/documents?student_id={student.public_id}")
    assert listed.status_code == 200
    assert len(listed.json()["data"]["results"]) == 1


@pytest.mark.django_db
def test_upload_rejects_bad_content_type_and_missing_owner(
    api_client, organization, user_factory, school_factory, student_factory,
):
    school = school_factory(organization=organization)
    student = student_factory(school=school)

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "documents.create")
    _login(api_client, "a@example.com", "s3cret-pass!")

    bad_type = api_client.post(
        "/api/v1/documents/upload",
        {
            "school": str(school.public_id), "document_type": "misc", "title": "Suspicious",
            "student": str(student.public_id),
            "file": SimpleUploadedFile("payload.exe", b"MZ\x90\x00", content_type="application/x-msdownload"),
        },
        format="multipart",
    )
    assert bad_type.status_code == 400

    mismatched_magic = api_client.post(
        "/api/v1/documents/upload",
        {
            "school": str(school.public_id), "document_type": "misc", "title": "Fake PDF",
            "student": str(student.public_id),
            "file": SimpleUploadedFile("fake.pdf", b"not really a pdf", content_type="application/pdf"),
        },
        format="multipart",
    )
    assert mismatched_magic.status_code == 400

    no_owner = api_client.post(
        "/api/v1/documents/upload",
        {
            "school": str(school.public_id), "document_type": "misc", "title": "Orphan",
            "file": SimpleUploadedFile("doc.pdf", _PDF_BYTES, content_type="application/pdf"),
        },
        format="multipart",
    )
    assert no_owner.status_code == 400


@pytest.mark.django_db
def test_documents_app_layer_tenant_isolation(
    organization, other_organization, school_factory, student_factory, document_factory,
):
    school_a = school_factory(organization=organization)
    school_b = school_factory(organization=other_organization)
    document_factory(school=school_a, student=student_factory(school=school_a))
    document_factory(school=school_b, student=student_factory(school=school_b))

    activate_organization(organization.id)
    visible = Document.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id
