from django.db import models

from apps.core.models import BaseModel


class Organization(BaseModel):
    """The tenant isolation boundary (§7 ARCHITECTURE.md). Not itself
    tenant-scoped — uses the plain default manager."""

    name = models.CharField(max_length=255)
    currency_code = models.CharField(max_length=3, default="NGN")
    timezone = models.CharField(max_length=64, default="UTC")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "tenancy_organization"

    def __str__(self) -> str:
        return self.name
