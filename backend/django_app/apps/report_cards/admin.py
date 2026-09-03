from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import TenantAdminMixin

from .models import ReportCard, ReportCardSubject, ReportCardWeighting


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
    ]
    list_filter = ["status", "term"]
    search_fields = ["student__first_name", "student__last_name", "report_card_number"]
    autocomplete_fields = ["organization", "student", "academic_year", "term", "class_level", "class_arm"]
    readonly_fields = [
        "report_card_number", "verification_code", "total_score", "total_possible_score",
        "average_percentage", "class_position", "class_size", "attendance_present",
        "attendance_absent", "attendance_percentage", "generated_at", "published_at",
    ]
    inlines = [ReportCardSubjectInline]

    # Calculated by report_card_service.generate_report_card, not hand-editable.
    def has_add_permission(self, request):
        return False


@admin.register(ReportCardWeighting)
class ReportCardWeightingAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["school", "ca_weight", "cbt_weight", "exam_weight"]
    autocomplete_fields = ["organization", "school"]
