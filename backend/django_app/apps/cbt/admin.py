from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.core.admin import TenantAdminMixin, TenantFKAdminMixin

from .models import (
    CBTExam,
    CBTMedia,
    ExamCandidate,
    ExamQuestion,
    ExamSection,
    Question,
    QuestionBlock,
    QuestionOption,
    QuestionVersion,
    Topic,
)


@admin.register(Topic)
class TopicAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "subject", "is_active"]
    search_fields = ["name"]
    autocomplete_fields = ["organization", "subject"]


class QuestionBlockInline(TabularInline):
    model = QuestionBlock
    extra = 0
    fields = ["block_type", "content", "order"]
    ordering = ["order"]


class QuestionOptionInline(TabularInline):
    model = QuestionOption
    extra = 0
    fields = ["label", "content", "is_correct", "order"]
    ordering = ["order"]


@admin.register(Question)
class QuestionAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["code", "subject", "class_level", "question_type", "difficulty", "marks", "status"]
    list_filter = ["question_type", "difficulty", "status"]
    search_fields = ["code"]
    autocomplete_fields = ["organization", "subject", "class_level", "topic", "approved_by"]
    inlines = [QuestionBlockInline, QuestionOptionInline]


@admin.register(QuestionVersion)
class QuestionVersionAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["question", "version_number", "created_at"]
    autocomplete_fields = ["organization", "question"]


@admin.register(CBTMedia)
class CBTMediaAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "media_type", "content_type", "size_bytes", "created_at"]
    list_filter = ["media_type"]
    search_fields = ["name"]
    autocomplete_fields = ["organization"]


class ExamQuestionInline(TenantFKAdminMixin, TabularInline):
    model = ExamQuestion
    extra = 0
    fields = ["question", "section", "order", "marks_override"]
    ordering = ["order"]
    autocomplete_fields = ["question", "section"]


class ExamSectionInline(TabularInline):
    model = ExamSection
    extra = 0
    fields = ["name", "order", "marks"]
    ordering = ["order"]


class ExamCandidateInline(TenantFKAdminMixin, TabularInline):
    model = ExamCandidate
    extra = 0
    fields = ["student", "candidate_number", "extra_time_minutes", "is_eligible"]
    autocomplete_fields = ["student"]


@admin.register(CBTExam)
class CBTExamAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["code", "name", "subject", "class_level", "exam_type", "status", "start_at", "end_at"]
    list_filter = ["exam_type", "status"]
    search_fields = ["code", "name"]
    autocomplete_fields = ["organization", "school", "academic_year", "term", "subject", "class_level"]
    inlines = [ExamSectionInline, ExamQuestionInline, ExamCandidateInline]


@admin.register(ExamSection)
class ExamSectionAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["exam", "name", "order", "marks"]
    search_fields = ["name"]
    autocomplete_fields = ["organization", "exam"]


@admin.register(ExamQuestion)
class ExamQuestionAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["exam", "question", "section", "order"]
    autocomplete_fields = ["organization", "exam", "section", "question"]


@admin.register(ExamCandidate)
class ExamCandidateAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["exam", "student", "candidate_number", "is_eligible"]
    search_fields = ["candidate_number"]
    autocomplete_fields = ["organization", "exam", "student"]
