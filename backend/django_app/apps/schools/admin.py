from django.contrib import admin

from apps.core.admin import TenantAdminMixin

from .models import AcademicYear, Campus, Department, School, Term


@admin.register(School)
class SchoolAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["name", "code", "organization", "is_active"]
    search_fields = ["name", "code"]
    list_filter = ["is_active", "organization"]


@admin.register(Campus)
class CampusAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["name", "code", "school"]
    search_fields = ["name", "code"]
    list_filter = ["school"]


@admin.register(AcademicYear)
class AcademicYearAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["name", "school", "is_active"]
    list_filter = ["is_active", "school"]


@admin.register(Term)
class TermAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["name", "academic_year", "sequence"]
    list_filter = ["academic_year"]


@admin.register(Department)
class DepartmentAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["name", "code", "school"]
    search_fields = ["name", "code"]
    list_filter = ["school"]
