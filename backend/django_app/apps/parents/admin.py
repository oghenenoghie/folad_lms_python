from django.contrib import admin

from apps.core.admin import TenantAdminMixin

from .models import Guardian, GuardianStudent


@admin.register(Guardian)
class GuardianAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["first_name", "last_name", "phone", "email"]
    search_fields = ["first_name", "last_name", "phone", "email"]


@admin.register(GuardianStudent)
class GuardianStudentAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["guardian", "student", "relationship_type", "is_primary_contact"]
    list_filter = ["relationship_type", "is_primary_contact"]
