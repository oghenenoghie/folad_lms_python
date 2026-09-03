from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import TenantAdminMixin

from .models import (
    ReportCard,
    ReportCardAudit,
    ReportCardBulkExport,
    ReportCardSubject,
    ReportCardWeighting,
)


class ReportCardSubjectInline(admin.TabularInline):
    model = ReportCardSubject
    extra = 0
    autocomplete_fields = ["organization", "subject"]
    readonly_fields = [
        "ca_score", "ca_max_score", "cbt_score", "cbt_max_score", "exam_score", "exam_max_score",
        "total_score", "percentage", "grade", "class_position",
    ]


@admin.register(ReportCard)
class ReportCardAdmin(TenantAdminMixin, ModelAdmin):
    list_display = [
        "student", "academic_year", "term", "average_percentage", "class_position", "status",
        "pdf_status",
    ]
    list_filter = ["status", "pdf_status", "term"]
    search_fields = ["student__first_name", "student__last_name", "report_card_number"]
    autocomplete_fields = ["organization", "student", "academic_year", "term", "class_level", "class_arm"]
    readonly_fields = [
        "report_card_number", "verification_code", "total_score", "total_possible_score",
        "average_percentage", "class_position", "class_size", "attendance_present",
        "attendance_absent", "attendance_percentage", "generated_at", "published_at",
        "pdf_status", "pdf_file_url", "pdf_generated_at", "pdf_error_message",
    ]
    inlines = [ReportCardSubjectInline]

    # Calculated by report_card_service.generate_report_card, not hand-editable.
    def has_add_permission(self, request):
        return False


@admin.register(ReportCardWeighting)
class ReportCardWeightingAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["school", "ca_weight", "cbt_weight", "exam_weight"]
    autocomplete_fields = ["organization", "school"]


@admin.register(ReportCardBulkExport)
class ReportCardBulkExportAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["term", "class_arm", "status", "report_card_count", "failed_count", "created_by"]
    list_filter = ["status", "term"]
    autocomplete_fields = ["organization", "term", "class_arm", "created_by"]
    readonly_fields = [
        "status", "report_card_count", "failed_count", "file_url", "error_message",
        "started_at", "completed_at",
    ]

    # Only ever produced by report_card_bulk_export_service.request_bulk_export.
    def has_add_permission(self, request):
        return False


@admin.register(ReportCardAudit)
class ReportCardAuditAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["report_card", "action", "previous_status", "new_status", "changed_by", "created_at"]
    list_filter = ["action", "new_status"]
    autocomplete_fields = ["organization", "report_card", "changed_by"]

    # Append-only at the DB layer (apps.tenancy.db.make_append_only) — the
    # trigger would reject a save/delete from here too, but hiding the
    # actions is a better failure mode than a 500 from Admin's own UI.
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
