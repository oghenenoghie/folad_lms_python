"""§4/§6 ARCHITECTURE.md. Student hangs off School; GuardianStudent is the
through-model for the many-to-many between Student and
`apps.parents.Guardian`, carrying `relationship_type`. Both models
denormalize `organization` directly — same convention as apps.schools and
apps.parents, required because TenantManager/enable_rls() key on a literal
`organization_id` column. `organization`/`school` are always derived
server-side, never accepted from client input.
"""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.tenancy.managers import TenantManager


class Student(BaseModel):
    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"

    class EnrollmentStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        GRADUATED = "graduated", "Graduated"
        WITHDRAWN = "withdrawn", "Withdrawn"
        SUSPENDED = "suspended", "Suspended"

    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="students")
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="student_profile",
    )
    admission_number = models.CharField(max_length=50)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True, default="")
    enrollment_status = models.CharField(
        max_length=20, choices=EnrollmentStatus.choices, default=EnrollmentStatus.ACTIVE
    )

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "students_student"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "admission_number"], name="uq_student_school_admission_number"
            )
        ]
        ordering = ["last_name", "first_name"]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"


class GuardianStudent(BaseModel):
    class RelationshipType(models.TextChoices):
        FATHER = "father", "Father"
        MOTHER = "mother", "Mother"
        GUARDIAN = "guardian", "Guardian"
        SIBLING = "sibling", "Sibling"
        OTHER = "other", "Other"

    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="guardian_links")
    guardian = models.ForeignKey("parents.Guardian", on_delete=models.PROTECT, related_name="student_links")
    relationship_type = models.CharField(max_length=20, choices=RelationshipType.choices)
    is_primary = models.BooleanField(default=False)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "students_guardian_student"
        constraints = [
            models.UniqueConstraint(fields=["student", "guardian"], name="uq_guardian_student_pair")
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.guardian} -> {self.student} ({self.relationship_type})"
