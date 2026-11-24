from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import TenantAdminMixin

from .models import ClassArm, ClassLevel, ClassSubject, Enrollment, Subject


@admin.register(ClassLevel)
class ClassLevelAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "campus", "sequence", "is_active"]
    search_fields = ["name"]
    list_filter = ["campus", "is_active"]
    autocomplete_fields = ["organization", "campus"]


@admin.register(ClassArm)
class ClassArmAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "class_level", "is_active"]
    search_fields = ["name"]
    list_filter = ["class_level", "is_active"]
    autocomplete_fields = ["organization", "class_level"]


@admin.register(Subject)
class SubjectAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "code", "school", "is_active"]
    search_fields = ["name", "code"]
    list_filter = ["school", "is_active"]
    autocomplete_fields = ["organization", "school"]


@admin.register(ClassSubject)
class ClassSubjectAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["class_arm", "subject", "teacher", "is_active"]
    search_fields = ["class_arm__name", "subject__name"]
    list_filter = ["is_active"]
    autocomplete_fields = ["organization", "class_arm", "subject", "teacher"]


@admin.register(Enrollment)
class EnrollmentAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["student", "class_arm", "academic_year", "status"]
    search_fields = ["student__first_name", "student__last_name", "student__admission_number"]
    list_filter = ["status", "academic_year", "class_arm"]
    autocomplete_fields = ["organization", "student", "class_arm", "academic_year"]
