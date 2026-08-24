"""§4/§5/§18 ARCHITECTURE.md (Milestone 4: guardian<->student links). A
Guardian is org-level, not school-level (§4 ERD: GUARDIAN has no direct
school FK) — one guardian's children can attend different schools within
the same organization. `GuardianStudent` is the through-table carrying the
relationship type; both models denormalize `organization` directly,
matching every other tenant-owned model (TenantManager and enable_rls()
key on a literal `organization_id` column).
"""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.tenancy.managers import TenantManager

RELATIONSHIP_TYPE_CHOICES = [
    ("father", "Father"),
    ("mother", "Mother"),
    ("guardian", "Guardian"),
    ("sibling", "Sibling"),
    ("other", "Other"),
]


class Guardian(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="guardian_profile",
    )
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=32, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    occupation = models.CharField(max_length=150, blank=True, default="")

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "parents_guardian"
        ordering = ["last_name", "first_name"]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"


class GuardianStudent(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    guardian = models.ForeignKey(Guardian, on_delete=models.PROTECT, related_name="guardian_links")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="guardian_links")
    relationship_type = models.CharField(
        max_length=20, choices=RELATIONSHIP_TYPE_CHOICES, default="guardian"
    )
    is_primary_contact = models.BooleanField(default=False)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "parents_guardian_student"
        constraints = [
            models.UniqueConstraint(fields=["guardian", "student"], name="uq_guardian_student")
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.guardian} -> {self.student} ({self.relationship_type})"
