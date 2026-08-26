from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import TenantAdminMixin

from .models import Guardian, GuardianStudent


@admin.register(Guardian)
class GuardianAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["first_name", "last_name", "phone", "email"]
    search_fields = ["first_name", "last_name", "phone", "email"]
    autocomplete_fields = ["organization", "user"]


@admin.register(GuardianStudent)
class GuardianStudentAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["guardian", "student", "relationship_type", "is_primary"]
    list_filter = ["relationship_type", "is_primary"]
    autocomplete_fields = ["organization", "guardian", "student"]
