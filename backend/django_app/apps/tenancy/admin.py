from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Organization


@admin.register(Organization)
class OrganizationAdmin(ModelAdmin):
    list_display = ["name", "currency_code", "timezone", "is_active"]
    search_fields = ["name"]
    list_filter = ["is_active"]
    # Not tenant-scoped (see Organization's own docstring), so no
    # TenantAdminMixin — but still a BaseModel, so the same read-only
    # treatment for the audit FKs applies here too.
    readonly_fields = ["created_by", "updated_by"]
