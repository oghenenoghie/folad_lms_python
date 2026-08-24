from django.contrib import admin

from apps.core.admin import TenantAdminMixin

from .models import Student


@admin.register(Student)
class StudentAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["admission_number", "first_name", "last_name", "school", "enrollment_status"]
    search_fields = ["admission_number", "first_name", "last_name"]
    list_filter = ["enrollment_status", "school"]
