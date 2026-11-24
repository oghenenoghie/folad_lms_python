from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import TenantAdminMixin

from .models import (
    Discount,
    FeeItem,
    FeeStructure,
    Invoice,
    InvoiceLine,
    LedgerEntry,
    Payment,
    Receipt,
    Refund,
    Scholarship,
)


@admin.register(FeeStructure)
class FeeStructureAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "school", "term", "is_active"]
    search_fields = ["name"]
    list_filter = ["is_active"]
    autocomplete_fields = ["organization", "school", "academic_year", "term"]


@admin.register(FeeItem)
class FeeItemAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "fee_structure", "amount_minor", "is_mandatory"]
    search_fields = ["name"]
    autocomplete_fields = ["organization", "fee_structure"]


@admin.register(Discount)
class DiscountAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "school", "discount_type", "percentage", "fixed_amount_minor", "is_active"]
    search_fields = ["name"]
    list_filter = ["discount_type", "is_active"]
    autocomplete_fields = ["organization", "school"]


@admin.register(Scholarship)
class ScholarshipAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["student", "discount", "academic_year", "is_active"]
    search_fields = ["student__first_name", "student__last_name"]
    autocomplete_fields = ["organization", "school", "student", "discount", "academic_year"]


@admin.register(Invoice)
class InvoiceAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["invoice_number", "student", "term", "total_minor", "status"]
    search_fields = ["invoice_number", "student__first_name", "student__last_name"]
    list_filter = ["status"]
    autocomplete_fields = ["organization", "school", "student", "academic_year", "term"]


@admin.register(InvoiceLine)
class InvoiceLineAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["invoice", "description", "quantity", "unit_amount_minor", "amount_minor"]
    autocomplete_fields = ["organization", "invoice", "fee_item", "discount"]


@admin.register(Payment)
class PaymentAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["reference", "invoice", "amount_minor", "method", "status", "paid_at"]
    search_fields = ["reference"]
    list_filter = ["method", "status"]
    autocomplete_fields = ["organization", "school", "invoice"]


@admin.register(Refund)
class RefundAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["payment", "amount_minor", "status", "processed_at"]
    list_filter = ["status"]
    autocomplete_fields = ["organization", "school", "payment"]


@admin.register(Receipt)
class ReceiptAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["receipt_number", "payment", "status", "generated_at"]
    search_fields = ["receipt_number"]
    list_filter = ["status"]
    autocomplete_fields = ["organization", "school", "payment"]

    # Generated only by the Celery task (apps.finance.tasks.reports) —
    # same rationale as apps.examinations.admin.ReportCardAdmin.
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(LedgerEntry)
class LedgerEntryAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["account", "debit_minor", "credit_minor", "ref_type", "ref_id", "created_at"]
    search_fields = ["account", "ref_type"]
    list_filter = ["account", "ref_type"]
    autocomplete_fields = ["organization", "school"]

    # Append-only at the DB layer (apps.tenancy.db.make_append_only) — see
    # the same rationale on apps.attendance.admin.AttendanceAuditAdmin.
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
