"""§4/§6 ARCHITECTURE.md. Staff hangs off School (and optionally
schools.Department); Teacher is a one-to-one specialization of Staff
("STAFF ||--o| TEACHER : is" in the ERD) — CASCADE on `staff` because it's
an extension row with no independent existence, unlike the PROTECT used
for cross-entity FKs elsewhere in this app. Both models denormalize
`organization` directly, same convention as apps.schools/apps.students.

Field names (`employee_number`, `position`, `date_joined`, the three-way
`employment_status`) and the `staff_id`-filterable Teacher list match the
already-shipped frontend's Staff & Teachers module contract (see
frontend/src/lib/staff.ts, staff-forms.ts, actions/staff.ts) — this app
was independently reconciled against that contract during a merge, not
authored against it directly.
"""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.tenancy.managers import TenantManager


class Staff(BaseModel):
    class EmploymentStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        ON_LEAVE = "on_leave", "On leave"
        TERMINATED = "terminated", "Terminated"

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
        on_delete=models.SET_NULL,
        related_name="staff_profile",
    )
    employee_number = models.CharField(max_length=50)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=32, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    position = models.CharField(max_length=100, blank=True, default="")
    employment_status = models.CharField(
        max_length=20, choices=EmploymentStatus.choices, default=EmploymentStatus.ACTIVE
    )
    date_joined = models.DateField(null=True, blank=True)

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
        return f"{self.first_name} {self.last_name}"


class Teacher(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    staff = models.OneToOneField(Staff, on_delete=models.CASCADE, related_name="teacher_profile")
    qualification = models.CharField(max_length=255, blank=True, default="")
    specialization = models.CharField(max_length=150, blank=True, default="")

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "staff_teacher"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return str(self.staff)
