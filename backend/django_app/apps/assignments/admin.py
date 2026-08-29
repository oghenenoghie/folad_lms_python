from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import TenantAdminMixin

from .models import Assignment, AssignmentSubmission


@admin.register(Assignment)
class AssignmentAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["title", "class_subject", "term", "due_date", "max_score"]
    search_fields = ["title"]
    autocomplete_fields = ["organization", "class_subject", "term"]


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["student", "assignment", "status", "score", "submitted_at"]
    search_fields = ["student__first_name", "student__last_name"]
    list_filter = ["status"]
    autocomplete_fields = ["organization", "assignment", "student"]
