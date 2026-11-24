from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import TenantAdminMixin

from .models import AcademicYear, Campus, Department, School, Term


@admin.register(School)
class SchoolAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "code", "organization", "is_active"]
    search_fields = ["name", "code"]
    list_filter = ["is_active", "organization"]
    autocomplete_fields = ["organization"]


@admin.register(Campus)
class CampusAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "code", "school"]
    search_fields = ["name", "code"]
    list_filter = ["school"]
    autocomplete_fields = ["organization", "school"]


@admin.register(AcademicYear)
class AcademicYearAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "school", "is_active"]
    search_fields = ["name"]
    list_filter = ["is_active", "school"]
    autocomplete_fields = ["organization", "school"]


@admin.register(Term)
class TermAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "academic_year", "sequence"]
    search_fields = ["name"]
    list_filter = ["academic_year"]
    autocomplete_fields = ["organization", "academic_year"]


@admin.register(Department)
class DepartmentAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "code", "school"]
    search_fields = ["name", "code"]
    list_filter = ["school"]
    autocomplete_fields = ["organization", "school"]
