"""§4/§5/§18 ARCHITECTURE.md (Milestone 5: classes, sections, subjects,
enrollment). Hierarchy: Campus -> ClassLevel (grade) -> ClassArm
(section/stream); Subject hangs off School (curriculum is school-wide);
ClassSubject is the arm x subject x teacher assignment; Enrollment ties a
Student to a ClassArm for one AcademicYear. Every model denormalizes
`organization` directly, same convention as every other app — both
TenantManager and enable_rls() key on a literal `organization_id` column.
`organization` is always derived server-side from the parent, never
accepted from client input.
"""
from django.db import models

from apps.core.models import BaseModel
from apps.tenancy.managers import TenantManager

ENROLLMENT_STATUS_CHOICES = [
    ("active", "Active"),
    ("transferred", "Transferred"),
    ("withdrawn", "Withdrawn"),
    ("completed", "Completed"),
]


class ClassLevel(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    campus = models.ForeignKey("schools.Campus", on_delete=models.PROTECT, related_name="class_levels")
    name = models.CharField(max_length=100)
    sequence = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "academics_class_level"
        constraints = [
            models.UniqueConstraint(fields=["campus", "name"], name="uq_class_level_campus_name")
        ]
        ordering = ["campus", "sequence"]

    def __str__(self) -> str:
        return self.name


class ClassArm(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    class_level = models.ForeignKey(ClassLevel, on_delete=models.PROTECT, related_name="class_arms")
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "academics_class_arm"
        constraints = [
            models.UniqueConstraint(fields=["class_level", "name"], name="uq_class_arm_level_name")
        ]
        ordering = ["class_level", "name"]

    def __str__(self) -> str:
        return f"{self.class_level} {self.name}"


class Subject(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="subjects")
    name = models.CharField(max_length=150)
    # Optional: left blank, save() derives one from `name` (e.g. "MAT" for
    # "Mathematics") — see apps.core.codegen.
    code = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "academics_subject"
        constraints = [models.UniqueConstraint(fields=["school", "code"], name="uq_subject_school_code")]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.code:
            from apps.core.codegen import next_abbreviation_code

            self.code = next_abbreviation_code(
                queryset=Subject.all_tenants.filter(school_id=self.school_id),
                field_name="code",
                name=self.name,
            )
        super().save(*args, **kwargs)


class ClassSubject(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    class_arm = models.ForeignKey(ClassArm, on_delete=models.PROTECT, related_name="class_subjects")
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="class_subjects")
    teacher = models.ForeignKey(
        "staff.Teacher", on_delete=models.PROTECT, related_name="class_subjects"
    )
    is_active = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "academics_class_subject"
        constraints = [
            models.UniqueConstraint(fields=["class_arm", "subject"], name="uq_class_subject_arm_subject")
        ]
        ordering = ["class_arm", "subject"]

    def __str__(self) -> str:
        return f"{self.class_arm} - {self.subject}"


class Enrollment(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="enrollments")
    class_arm = models.ForeignKey(ClassArm, on_delete=models.PROTECT, related_name="enrollments")
    academic_year = models.ForeignKey(
        "schools.AcademicYear", on_delete=models.PROTECT, related_name="enrollments"
    )
    status = models.CharField(max_length=20, choices=ENROLLMENT_STATUS_CHOICES, default="active")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "academics_enrollment"
        constraints = [
            # A student holds exactly one enrollment per academic year — the
            # M5 exit criterion (§18 ARCHITECTURE.md: "Enrollment with
            # duplicate-prevention constraints"). A mid-year class-arm
            # transfer updates this row rather than creating a second one.
            models.UniqueConstraint(
                fields=["student", "academic_year"], name="uq_enrollment_student_year"
            )
        ]
        ordering = ["-academic_year", "class_arm"]

    def __str__(self) -> str:
        return f"{self.student} -> {self.class_arm} ({self.academic_year})"
