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
    per §4 ARCHITECTURE.md's ERD (USER ||--o| STUDENT : profile) a student
    doesn't strictly need one — but student_service.create_student()
    auto-provisions a login for every new student that doesn't already
    have one (see provision_login()), using `email` when given or a
    generated placeholder address otherwise. Null stays reachable for a
    student explicitly linked to an existing account instead.
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
    # Optional: left blank, save() assigns the next sequential number for
    # this school (e.g. "TS-0001") — see apps.core.codegen.
    admission_number = models.CharField(max_length=30, blank=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True, default="")
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, default="")
    enrollment_status = models.CharField(
        max_length=20, choices=ENROLLMENT_STATUS_CHOICES, default="active"
    )
    # A storage key (apps.core.storage), not a Django FileField — the
    # default file storage is local-filesystem-only outside S3
    # (STORAGE_BACKEND), which would silently lose the photo on every
    # production redeploy. Same pattern as apps.documents/apps.assignments.
    photo_storage_key = models.CharField(max_length=500, blank=True, default="")

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

    def save(self, *args, **kwargs):
        if not self.admission_number:
            from apps.core.codegen import next_sequence_code

            self.admission_number = next_sequence_code(
                queryset=Student.all_tenants.filter(school_id=self.school_id),
                field_name="admission_number",
                prefix=f"{self.school.code}-",
            )
        super().save(*args, **kwargs)
