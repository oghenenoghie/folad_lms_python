from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import TenantAdminMixin

from .models import Hostel, HostelAllocation, HostelBed, HostelBuilding, HostelIncident, HostelRoom


@admin.register(Hostel)
class HostelAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "school", "hostel_type", "warden"]
    search_fields = ["name"]
    list_filter = ["hostel_type"]
    autocomplete_fields = ["organization", "school", "warden"]


@admin.register(HostelBuilding)
class HostelBuildingAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "hostel"]
    search_fields = ["name"]
    autocomplete_fields = ["organization", "hostel"]


@admin.register(HostelRoom)
class HostelRoomAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["room_number", "building", "capacity"]
    search_fields = ["room_number"]
    autocomplete_fields = ["organization", "building"]


@admin.register(HostelBed)
class HostelBedAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["bed_number", "room", "status"]
    search_fields = ["bed_number"]
    list_filter = ["status"]
    autocomplete_fields = ["organization", "room"]


@admin.register(HostelAllocation)
class HostelAllocationAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["student", "bed", "academic_year", "is_active"]
    search_fields = ["student__first_name", "student__last_name"]
    list_filter = ["is_active"]
    autocomplete_fields = ["organization", "student", "bed", "academic_year"]


@admin.register(HostelIncident)
class HostelIncidentAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["hostel", "description", "severity", "status", "occurred_at"]
    search_fields = ["description"]
    list_filter = ["severity", "status"]
    autocomplete_fields = ["organization", "hostel", "room", "student", "reported_by"]
