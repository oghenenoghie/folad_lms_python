"""Thin views, fat services (§11 ARCHITECTURE.md). upload_document() is
§14's upload path end to end: validate -> store under a tenant-scoped key
-> persist metadata. Exactly one of `student`/`staff` is ever passed —
`owner_type` is derived from which one, never accepted as separate client
input, so it can't drift from the actual link (the DB check constraint in
models.py backs this up too).
"""
from django.utils import timezone

from apps.core.storage import get_presigned_download_url, save_document, validate_upload
from apps.documents.models import Document
from apps.documents.services.exceptions import DocumentError
from apps.schools.models import School
from apps.staff.models import Staff
from apps.students.models import Student


def upload_document(
    *, school: School, actor, document_type: str, title: str, file_name: str, content: bytes,
    content_type: str, student: Student | None = None, staff: Staff | None = None,
) -> Document:
    if bool(student) == bool(staff):
        raise DocumentError("exactly one of student or staff must be provided")
    validate_upload(content=content, content_type=content_type)
    storage_key = save_document(
        key_prefix=f"documents/{school.organization_id}",
        filename=file_name,
        content=content,
        content_type=content_type,
    )
    return Document.objects.create(
        organization=school.organization,
        school=school,
        owner_type="student" if student else "staff",
        student=student,
        staff=staff,
        document_type=document_type,
        title=title,
        storage_key=storage_key,
        file_name=file_name,
        content_type=content_type,
        size_bytes=len(content),
        uploaded_by=actor,
        created_by=actor,
        updated_by=actor,
    )


def update_document(*, document: Document, actor, **fields) -> Document:
    for field, value in fields.items():
        setattr(document, field, value)
    document.updated_by = actor
    document.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return document


def delete_document(*, document: Document, actor) -> None:
    document.deleted_at = timezone.now()
    document.updated_by = actor
    document.save(update_fields=["deleted_at", "updated_by", "updated_at"])


def get_download_url(document: Document) -> str:
    return get_presigned_download_url(document.storage_key)
