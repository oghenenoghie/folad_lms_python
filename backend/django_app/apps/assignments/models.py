"""§4/§6/§18 ARCHITECTURE.md (Milestone 10). Assignment is a homework/project
set on a ClassSubject for a term; AssignmentSubmission is one student's
answer to it — either free-text (`text_content`) or a file, whichever the
student used. A submission carries its own storage fields rather than a FK
to `apps.documents.Document`: keeping assignments and documents decoupled
avoids a cross-app migration dependency for what is, functionally, just one
more place §14's upload path (validate -> store under a tenant-scoped key ->
persist metadata) gets applied — see apps.core.storage for the shared
validation/storage helpers both apps call into. Every model
denormalizes `organization` directly, same convention as every other app.
"""
from django.db import models

from apps.core.models import BaseModel
from apps.tenancy.managers import TenantManager

SUBMISSION_STATUS_CHOICES = [
    ("submitted", "Submitted"),
    ("late", "Late"),
    ("graded", "Graded"),
]


class Assignment(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    class_subject = models.ForeignKey(
        "academics.ClassSubject", on_delete=models.PROTECT, related_name="assignments"
    )
    term = models.ForeignKey("schools.Term", on_delete=models.PROTECT, related_name="assignments")
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, default="")
    due_date = models.DateField()
    max_score = models.DecimalField(max_digits=5, decimal_places=2)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "assignments_assignment"
        constraints = [
            models.UniqueConstraint(
                fields=["class_subject", "term", "title"], name="uq_assignment_subject_term_title"
            )
        ]
        ordering = ["-due_date"]

    def __str__(self) -> str:
        return self.title


class AssignmentSubmission(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    assignment = models.ForeignKey(Assignment, on_delete=models.PROTECT, related_name="submissions")
    student = models.ForeignKey(
        "students.Student", on_delete=models.PROTECT, related_name="assignment_submissions"
    )
    text_content = models.TextField(blank=True, default="")
    storage_key = models.CharField(max_length=500, blank=True, default="")
    file_name = models.CharField(max_length=255, blank=True, default="")
    content_type = models.CharField(max_length=100, blank=True, default="")
    size_bytes = models.PositiveIntegerField(null=True, blank=True)
    submitted_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=SUBMISSION_STATUS_CHOICES, default="submitted")
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True, default="")
    graded_at = models.DateTimeField(null=True, blank=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "assignments_submission"
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "student"], name="uq_assignment_submission_assignment_student"
            )
        ]
        ordering = ["-submitted_at"]

    def __str__(self) -> str:
        return f"{self.student} -> {self.assignment}"
