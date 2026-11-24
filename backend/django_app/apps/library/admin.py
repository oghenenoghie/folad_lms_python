from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import TenantAdminMixin

from .models import LibraryBook, LibraryCopy, LibraryFine, LibraryLoan, LibraryMember


@admin.register(LibraryBook)
class LibraryBookAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["title", "author", "school", "category"]
    search_fields = ["title", "author", "isbn"]
    list_filter = ["category"]
    autocomplete_fields = ["organization", "school"]


@admin.register(LibraryCopy)
class LibraryCopyAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["book", "copy_number", "status"]
    search_fields = ["copy_number"]
    list_filter = ["status"]
    autocomplete_fields = ["organization", "book"]


@admin.register(LibraryMember)
class LibraryMemberAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["membership_number", "member_type", "school", "is_active"]
    search_fields = ["membership_number"]
    list_filter = ["member_type", "is_active"]
    autocomplete_fields = ["organization", "school", "student", "staff"]


@admin.register(LibraryLoan)
class LibraryLoanAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["member", "copy", "borrowed_date", "due_date", "status"]
    search_fields = ["member__membership_number"]
    list_filter = ["status"]
    autocomplete_fields = ["organization", "copy", "member"]


@admin.register(LibraryFine)
class LibraryFineAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["loan", "amount_minor", "status"]
    list_filter = ["status"]
    autocomplete_fields = ["organization", "loan"]
