from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import TenantAdminMixin

from .models import Attendance, AttendanceAudit


@admin.register(Attendance)
class AttendanceAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["enrollment", "date", "status"]
    search_fields = ["enrollment__student__first_name", "enrollment__student__last_name"]
    list_filter = ["status", "date"]
    autocomplete_fields = ["organization", "enrollment"]


@admin.register(AttendanceAudit)
class AttendanceAuditAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["attendance", "previous_status", "new_status", "changed_by", "created_at"]
    list_filter = ["new_status"]
    autocomplete_fields = ["organization", "attendance", "changed_by"]

    # Append-only at the DB layer (apps.tenancy.db.make_append_only) — the
    # trigger would reject a save/delete from here too, but hiding the
    # actions is a better failure mode than a 500 from Admin's own UI.
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
