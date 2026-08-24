"""§4/§5/§18 ARCHITECTURE.md (Milestone 4: HR access controls). `Teacher` is
a strict one-to-one specialization of `Staff` (§4 ERD: STAFF ||--o| TEACHER
: is) — a teacher is always staff first; non-teaching staff have no Teacher
row. Both models denormalize `organization` directly, matching every other
tenant-owned model (TenantManager and enable_rls() key on a literal
`organization_id` column).
"""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.tenancy.managers import TenantManager

EMPLOYMENT_STATUS_CHOICES = [
    ("active", "Active"),
    ("on_leave", "On Leave"),
    ("terminated", "Terminated"),
]


class Staff(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="staff_members")
    department = models.ForeignKey(
        "schools.Department",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="staff_members",
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="staff_profile",
    )
    employee_number = models.CharField(max_length=30)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    position = models.CharField(max_length=100)
    employment_status = models.CharField(
        max_length=20, choices=EMPLOYMENT_STATUS_CHOICES, default="active"
    )
    date_joined = models.DateField()

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "staff_staff"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "employee_number"], name="uq_staff_school_employee_number"
            )
        ]
        ordering = ["last_name", "first_name"]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} ({self.employee_number})"


class Teacher(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    staff = models.OneToOneField(Staff, on_delete=models.PROTECT, related_name="teacher_profile")
    qualification = models.CharField(max_length=150, blank=True, default="")
    specialization = models.CharField(max_length=150, blank=True, default="")

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "staff_teacher"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Teacher: {self.staff}"
