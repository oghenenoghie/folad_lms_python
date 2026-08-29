from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import TenantAdminMixin

from .models import (
    Assessment,
    Exam,
    ExamSchedule,
    GradeBand,
    GradingScheme,
    Invigilator,
    Question,
    QuestionOption,
    ReportCard,
    Result,
    ResultWorkflowState,
    StudentAnswer,
)


@admin.register(GradingScheme)
class GradingSchemeAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "school", "is_default"]
    search_fields = ["name"]
    list_filter = ["is_default"]
    autocomplete_fields = ["organization", "school"]


@admin.register(GradeBand)
class GradeBandAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["grading_scheme", "grade", "min_score", "max_score"]
    search_fields = ["grade"]
    autocomplete_fields = ["organization", "grading_scheme"]


@admin.register(Exam)
class ExamAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "school", "term", "start_date", "end_date"]
    search_fields = ["name"]
    list_filter = ["start_date"]
    autocomplete_fields = ["organization", "school", "academic_year", "term"]


@admin.register(ExamSchedule)
class ExamScheduleAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["exam", "class_subject", "date", "start_time", "end_time", "room"]
    search_fields = ["exam__name"]
    list_filter = ["date"]
    autocomplete_fields = ["organization", "exam", "class_subject", "room"]


@admin.register(Invigilator)
class InvigilatorAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["exam_schedule", "teacher"]
    autocomplete_fields = ["organization", "exam_schedule", "teacher"]


@admin.register(Assessment)
class AssessmentAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "class_subject", "term", "assessment_type", "weight", "max_score"]
    search_fields = ["name"]
    list_filter = ["assessment_type"]
    autocomplete_fields = ["organization", "class_subject", "term", "exam"]


@admin.register(Question)
class QuestionAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["assessment", "sequence", "question_type", "marks"]
    search_fields = ["text"]
    list_filter = ["question_type"]
    autocomplete_fields = ["organization", "assessment"]


@admin.register(QuestionOption)
class QuestionOptionAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["question", "sequence", "text", "is_correct"]
    search_fields = ["text"]
    autocomplete_fields = ["organization", "question"]


@admin.register(StudentAnswer)
class StudentAnswerAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["student", "question", "is_correct", "marks_awarded", "submitted_at"]
    search_fields = ["student__first_name", "student__last_name"]
    list_filter = ["is_correct"]
    autocomplete_fields = ["organization", "question", "student", "selected_option"]


@admin.register(Result)
class ResultAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["student", "assessment", "score", "grade", "status"]
    search_fields = ["student__first_name", "student__last_name"]
    list_filter = ["status"]
    autocomplete_fields = ["organization", "assessment", "student"]


@admin.register(ResultWorkflowState)
class ResultWorkflowStateAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["result", "previous_status", "new_status", "changed_by", "created_at"]
    list_filter = ["new_status"]
    autocomplete_fields = ["organization", "result", "changed_by"]

    # Append-only at the DB layer (apps.tenancy.db.make_append_only) — see
    # the same rationale on apps.attendance.admin.AttendanceAuditAdmin.
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReportCard)
class ReportCardAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["student", "term", "status", "generated_at"]
    search_fields = ["student__first_name", "student__last_name"]
    list_filter = ["status"]
    autocomplete_fields = ["organization", "student", "academic_year", "term"]

    # Generated only by the Celery task (apps.examinations.tasks.reports) —
    # Admin can inspect the row but must not hand-edit its generated state.
    def has_change_permission(self, request, obj=None):
        return False
