from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import TenantAdminMixin

from .models import Staff, Teacher


@admin.register(Staff)
class StaffAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["employee_number", "first_name", "last_name", "school", "position", "employment_status"]
    search_fields = ["employee_number", "first_name", "last_name"]
    list_filter = ["employment_status", "school", "department"]
    autocomplete_fields = ["organization", "school", "department", "user"]


@admin.register(Teacher)
class TeacherAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["staff", "qualification", "specialization"]
    search_fields = ["staff__first_name", "staff__last_name"]
    autocomplete_fields = ["organization", "staff"]
