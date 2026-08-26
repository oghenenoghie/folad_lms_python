"""§4/§5/§18 ARCHITECTURE.md (Milestone 4: admission -> profile). Denormalizes
`organization` directly (not just `school`), matching the pattern every
tenant-owned model under apps.schools already uses — both TenantManager and
enable_rls() key on a literal `organization_id` column. `organization` is
always derived server-side from `school`, never accepted from client input.
GuardianStudent (the student<->guardian link) lives in `apps.parents`, not
here — see that app's models.py.
"""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.tenancy.managers import TenantManager

ENROLLMENT_STATUS_CHOICES = [
    ("active", "Active"),
    ("inactive", "Inactive"),
    ("graduated", "Graduated"),
    ("withdrawn", "Withdrawn"),
    ("suspended", "Suspended"),
]

GENDER_CHOICES = [
    ("male", "Male"),
    ("female", "Female"),
    ("other", "Other"),
]


class Student(BaseModel):
    """A school's admission record for one learner. `user` is nullable —
    per §4 ARCHITECTURE.md's ERD (USER ||--o| STUDENT : profile), a student
    doesn't require a platform login account (e.g. a young child whose
    guardian manages everything); when one exists, it's a strict one-to-one.
    """

    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="students")
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="student_profile",
    )
    admission_number = models.CharField(max_length=30)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, default="")
    enrollment_status = models.CharField(
        max_length=20, choices=ENROLLMENT_STATUS_CHOICES, default="active"
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
        return f"{self.first_name} {self.last_name} ({self.admission_number})"
