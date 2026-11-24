from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import TenantAdminMixin

from .models import Period, Room, TimetableSlot


@admin.register(Room)
class RoomAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "campus", "capacity", "is_active"]
    search_fields = ["name"]
    list_filter = ["campus", "is_active"]
    autocomplete_fields = ["organization", "campus"]


@admin.register(Period)
class PeriodAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "school", "sequence", "start_time", "end_time", "is_active"]
    search_fields = ["name"]
    list_filter = ["school", "is_active"]
    autocomplete_fields = ["organization", "school"]


@admin.register(TimetableSlot)
class TimetableSlotAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["class_arm", "class_subject", "teacher", "room", "day_of_week", "period"]
    list_filter = ["day_of_week", "period", "is_active"]
    autocomplete_fields = ["organization", "class_subject", "class_arm", "teacher", "room", "period"]
