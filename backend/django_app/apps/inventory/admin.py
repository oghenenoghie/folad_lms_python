from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import TenantAdminMixin

from .models import InventoryItem, PurchaseOrder, StockMovement, Supplier


@admin.register(InventoryItem)
class InventoryItemAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "sku", "school", "quantity_on_hand", "reorder_level"]
    search_fields = ["name", "sku"]
    autocomplete_fields = ["organization", "school"]


@admin.register(Supplier)
class SupplierAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "school", "contact_email", "contact_phone"]
    search_fields = ["name"]
    autocomplete_fields = ["organization", "school"]


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["order_number", "supplier", "item", "quantity_ordered", "status"]
    search_fields = ["order_number"]
    list_filter = ["status"]
    autocomplete_fields = ["organization", "school", "supplier", "item"]


@admin.register(StockMovement)
class StockMovementAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["item", "movement_type", "quantity", "occurred_at"]
    list_filter = ["movement_type"]
    autocomplete_fields = ["organization", "item"]

    # Append-only at the DB layer (apps.tenancy.db.make_append_only) — same
    # rationale as apps.finance.admin.LedgerEntryAdmin.
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
