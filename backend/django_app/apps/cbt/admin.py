from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.core.admin import TenantAdminMixin

from .models import CBTMedia, Question, QuestionBlock, QuestionOption, QuestionVersion, Topic


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
