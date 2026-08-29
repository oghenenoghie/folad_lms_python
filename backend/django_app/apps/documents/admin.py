from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import TenantAdminMixin

from .models import Document


@admin.register(Document)
class DocumentAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["title", "owner_type", "student", "staff", "document_type", "content_type"]
    search_fields = ["title", "file_name"]
    list_filter = ["owner_type", "document_type"]
    autocomplete_fields = ["organization", "school", "student", "staff", "uploaded_by"]
