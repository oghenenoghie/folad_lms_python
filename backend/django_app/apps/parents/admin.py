from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import TenantAdminMixin

from .models import Guardian


@admin.register(Guardian)
class GuardianAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["first_name", "last_name", "phone", "email"]
    search_fields = ["first_name", "last_name", "phone", "email"]
    autocomplete_fields = ["organization", "user"]
