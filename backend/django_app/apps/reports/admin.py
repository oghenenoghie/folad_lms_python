from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import TenantAdminMixin

from .models import ReportRequest


@admin.register(ReportRequest)
class ReportRequestAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["report_type", "format", "school", "status", "requested_by", "created_at"]
    search_fields = ["report_type"]
    list_filter = ["report_type", "format", "status"]
    autocomplete_fields = ["organization", "school", "requested_by"]

    # Generated only by the Celery task (apps.reports.tasks.generation) —
    # same rationale as apps.examinations.admin.ReportCardAdmin.
    def has_change_permission(self, request, obj=None):
        return False
