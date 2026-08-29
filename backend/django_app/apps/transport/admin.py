from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import TenantAdminMixin

from .models import RouteStop, TransportAssignment, TransportRoute, Vehicle, VehicleMaintenance


@admin.register(Vehicle)
class VehicleAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["registration_number", "school", "capacity", "status"]
    search_fields = ["registration_number"]
    list_filter = ["status"]
    autocomplete_fields = ["organization", "school"]


@admin.register(TransportRoute)
class TransportRouteAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "school"]
    search_fields = ["name"]
    autocomplete_fields = ["organization", "school"]


@admin.register(RouteStop)
class RouteStopAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["route", "name", "sequence", "pickup_time"]
    search_fields = ["name"]
    autocomplete_fields = ["organization", "route"]


@admin.register(TransportAssignment)
class TransportAssignmentAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["student", "vehicle", "route", "stop", "is_active"]
    search_fields = ["student__first_name", "student__last_name"]
    list_filter = ["is_active"]
    autocomplete_fields = ["organization", "student", "vehicle", "route", "stop", "academic_year"]


@admin.register(VehicleMaintenance)
class VehicleMaintenanceAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["vehicle", "description", "scheduled_date", "status"]
    list_filter = ["status"]
    autocomplete_fields = ["organization", "vehicle"]
