"""Shared Django Admin utilities."""


class TenantAdminMixin:
    """Django Admin is a platform-level ops console (§11 ARCHITECTURE.md),
    not a tenant-scoped surface — staff need to see records across every
    organization, not just whichever one happens to be in the app-layer
    tenant context. That context is never set at all for admin's
    session-based auth (nothing calls activate_organization() there), so
    every model whose default `objects` manager is a tenant-scoped
    TenantManager (apps.tenancy.managers) would otherwise show an empty
    list in Django Admin — TenantManager.get_queryset() returns nothing
    with no context set. Mix this into any such model's ModelAdmin to use
    the unscoped `all_tenants` manager instead, mirroring the same
    escape hatch apps/accounts/managers.py's UserManager.get_by_natural_key
    and apps/accounts/authentication.py already use for the same reason.
    """

    # created_by/updated_by (TimestampedModel) are set programmatically by
    # the services layer, never by hand in the admin — read-only here so
    # they render as plain text instead of an editable FK widget.
    readonly_fields = ["created_by", "updated_by"]

    def get_queryset(self, request):
        qs = self.model.all_tenants.all()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs
