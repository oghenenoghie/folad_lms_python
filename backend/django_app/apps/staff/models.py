"""§4/§5/§18 ARCHITECTURE.md (Milestone 4: HR access controls). `Teacher` is
a one-to-one specialization of `Staff` (§4 ERD: STAFF ||--o| TEACHER : is).
Both models denormalize `organization` directly, same convention as
apps.schools/apps.students.

Field names (`employee_number`, `position`, `date_joined`, the three-way
`employment_status`) and the `staff_id`-filterable Teacher list match the
already-shipped frontend's Staff & Teachers module contract (see
frontend/src/lib/staff.ts, staff-forms.ts, actions/staff.ts).
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
    # Optional: left blank, save() assigns the next sequential number for
    # this school (e.g. "EMP-0001") — see apps.core.codegen.
    employee_number = models.CharField(max_length=30, blank=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    position = models.CharField(max_length=100)
    employment_status = models.CharField(
        max_length=20, choices=EMPLOYMENT_STATUS_CHOICES, default="active"
    )
    date_joined = models.DateField()
    phone = models.CharField(max_length=32, blank=True, default="")
    email = models.EmailField(blank=True, default="")

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

    def save(self, *args, **kwargs):
        if not self.employee_number:
            from apps.core.codegen import next_sequence_code

            self.employee_number = next_sequence_code(
                queryset=Staff.all_tenants.filter(school_id=self.school_id),
                field_name="employee_number",
                prefix="EMP-",
            )
        super().save(*args, **kwargs)


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
