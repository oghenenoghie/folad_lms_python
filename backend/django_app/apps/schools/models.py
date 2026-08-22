"""§5/§7 ARCHITECTURE.md. Hierarchy: Organization -> School -> Campus /
AcademicYear -> Term, plus Department under School. Every model here
denormalizes `organization` directly (not just its natural parent FK)
because both TenantManager and enable_rls() key on a literal
`organization_id` column — the same pattern accounts.LoginHistory already
uses for a model that isn't itself org-level. `organization` is always
derived server-side from the parent, never accepted from client input.
"""
from django.db import models

from apps.core.models import BaseModel
from apps.tenancy.managers import TenantManager


class School(BaseModel):
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="schools"
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20)
    address = models.CharField(max_length=255, blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    default_grading_scheme = models.CharField(max_length=100, blank=True, default="")
    is_active = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "schools_school"
        constraints = [models.UniqueConstraint(fields=["organization", "code"], name="uq_school_org_code")]

    def __str__(self) -> str:
        return self.name


class Campus(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="campuses")
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20)
    address = models.CharField(max_length=255, blank=True, default="")
    is_main = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "schools_campus"
        constraints = [models.UniqueConstraint(fields=["school", "code"], name="uq_campus_school_code")]

    def __str__(self) -> str:
        return self.name


class AcademicYear(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="academic_years")
    name = models.CharField(max_length=20)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "schools_academic_year"
        constraints = [
            models.UniqueConstraint(fields=["school", "name"], name="uq_academic_year_school_name")
        ]
        ordering = ["-start_date"]

    def __str__(self) -> str:
        return self.name


class Term(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="terms")
    name = models.CharField(max_length=50)
    sequence = models.PositiveSmallIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "schools_term"
        constraints = [
            models.UniqueConstraint(fields=["academic_year", "sequence"], name="uq_term_year_sequence"),
            models.UniqueConstraint(fields=["academic_year", "name"], name="uq_term_year_name"),
        ]
        ordering = ["academic_year", "sequence"]

    def __str__(self) -> str:
        return self.name


class Department(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="departments")
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20)
    description = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "schools_department"
        constraints = [
            models.UniqueConstraint(fields=["school", "code"], name="uq_department_school_code")
        ]

    def __str__(self) -> str:
        return self.name
