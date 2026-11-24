from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import TenantAdminMixin

from .models import Announcement, Message, Notification, NotificationPreference


@admin.register(Announcement)
class AnnouncementAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["title", "school", "audience", "is_pinned", "published_at"]
    search_fields = ["title"]
    list_filter = ["audience", "is_pinned"]
    autocomplete_fields = ["organization", "school"]


@admin.register(Notification)
class NotificationAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["recipient", "notification_type", "title", "is_read", "created_at"]
    search_fields = ["title"]
    list_filter = ["notification_type", "is_read"]
    autocomplete_fields = ["organization", "recipient"]


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["user", "email_enabled", "sms_enabled", "push_enabled", "in_app_enabled"]
    autocomplete_fields = ["organization", "user"]


@admin.register(Message)
class MessageAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["sender", "recipient", "subject", "is_read", "created_at"]
    search_fields = ["subject"]
    list_filter = ["is_read"]
    autocomplete_fields = ["organization", "sender", "recipient"]
