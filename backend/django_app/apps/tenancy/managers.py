"""App-layer tenant scoping (layer 2 of the defence-in-depth stack; see §7 ARCHITECTURE.md).

Every tenant-owned model uses `objects = TenantManager()` as its default
manager. Its queryset is always filtered to the organization resolved by
TenancyMiddleware for the current request. With no organization in
context, it fails closed (returns nothing) rather than leaking all rows.

`all_tenants` is the explicit escape hatch for platform-admin code paths
that must legitimately see across organizations (SUPER_ADMIN reporting,
migrations, management commands). Reach for it only there.
"""
from django.db import models

from .context import get_current_organization_id


class TenantQuerySet(models.QuerySet):
    def for_organization(self, organization_id: int) -> "TenantQuerySet":
        return self.filter(organization_id=organization_id)


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    def get_queryset(self) -> TenantQuerySet:
        org_id = get_current_organization_id()
        qs = super().get_queryset()
        if org_id is None:
            return qs.none()
        return qs.filter(organization_id=org_id)
