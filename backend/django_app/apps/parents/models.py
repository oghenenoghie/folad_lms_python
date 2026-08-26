"""§4/§6 ARCHITECTURE.md: Guardian is a standalone person record, optionally
linked to a login-capable `accounts.User` (the "profile" edge in the ERD),
and linked to zero or more Student records through
`apps.students.models.GuardianStudent`. `organization` is denormalized
directly on the row (not just reachable via `user`) because `user` is
optional and both TenantManager and enable_rls() key on a literal
`organization_id` column — same convention as apps.schools.
"""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.tenancy.managers import TenantManager


class Guardian(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="guardian_profile",
    )
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=32, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    occupation = models.CharField(max_length=150, blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "parents_guardian"

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"
