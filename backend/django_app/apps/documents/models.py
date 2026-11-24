"""§4/§6/§14/§18 ARCHITECTURE.md (Milestone 10). Binary files never live in
Postgres (§14) — only this metadata row does; the actual bytes sit in
object storage under `storage_key`, written/read via apps.core.storage.
`owner_type` + exactly one of `student`/`staff` set (same dual-ownership
check-constraint pattern as apps.library.LibraryMember) mirrors the ERD's
`STUDENT ||--o{ DOCUMENT : owns` / `STAFF ||--o{ DOCUMENT : owns`. No
`file_url` field: a stored URL would eventually point at an expired
presigned link, so downloads always compute a fresh one at request time
(see services/document_service.py) rather than persisting one that decays.
"""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.tenancy.managers import TenantManager

OWNER_TYPE_CHOICES = [
    ("student", "Student"),
    ("staff", "Staff"),
]


class Document(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="documents")
    owner_type = models.CharField(max_length=10, choices=OWNER_TYPE_CHOICES)
    student = models.ForeignKey(
        "students.Student", null=True, blank=True, on_delete=models.PROTECT, related_name="documents"
    )
    staff = models.ForeignKey(
        "staff.Staff", null=True, blank=True, on_delete=models.PROTECT, related_name="documents"
    )
    document_type = models.CharField(max_length=50)
    title = models.CharField(max_length=200)
    storage_key = models.CharField(max_length=500)
    file_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "documents_document"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(owner_type="student", student__isnull=False, staff__isnull=True)
                    | models.Q(owner_type="staff", staff__isnull=False, student__isnull=True)
                ),
                name="ck_document_owner_type_matches_link",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title
