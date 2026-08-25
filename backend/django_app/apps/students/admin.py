from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import TenantAdminMixin

from .models import Student


@admin.register(Student)
class StudentAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["admission_number", "first_name", "last_name", "school", "enrollment_status"]
    search_fields = ["admission_number", "first_name", "last_name"]
    list_filter = ["enrollment_status", "school"]
    autocomplete_fields = ["organization", "school", "user"]
