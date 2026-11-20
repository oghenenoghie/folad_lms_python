from rest_framework import serializers

from apps.accounts.models import User
from apps.core.serializers import PublicIdRelatedField
from apps.schools.models import School

from .models import Announcement, Message, Notification, NotificationPreference


class AnnouncementSerializer(serializers.ModelSerializer):
    school = PublicIdRelatedField(queryset=School.objects)

    class Meta:
        model = Announcement
        fields = ["public_id", "school", "title", "body", "audience", "is_pinned", "published_at"]
        read_only_fields = ["published_at"]


class NotificationSerializer(serializers.ModelSerializer):
    recipient = PublicIdRelatedField(read_only=True)

    class Meta:
        model = Notification
        fields = [
            "public_id", "recipient", "notification_type", "title", "body", "link_url",
            "ref_type", "ref_id", "is_read", "read_at", "created_at",
        ]
        read_only_fields = [
            "recipient", "notification_type", "title", "body", "link_url", "ref_type", "ref_id",
            "is_read", "read_at", "created_at",
        ]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    user = PublicIdRelatedField(read_only=True)

    class Meta:
        model = NotificationPreference
        fields = ["public_id", "user", "email_enabled", "sms_enabled", "push_enabled", "in_app_enabled"]
        read_only_fields = ["user"]


class MessageSerializer(serializers.ModelSerializer):
    sender = PublicIdRelatedField(read_only=True)
    # `User.objects` (the manager), not `.all()` — DRF's RelatedField
    # re-evaluates a bare manager's `.all()` lazily per-request, whereas a
    # pre-built queryset would freeze any org-scoping at import time (no
    # request context yet), permanently baking in an empty set.
    recipient = PublicIdRelatedField(queryset=User.objects)
    # sender/recipient above are opaque public_ids (PublicIdRelatedField),
    # and there's no general "look up a user by public_id" endpoint a
    # non-admin user can call to resolve one to a display name — these
    # give the inbox UI something to actually show, same formatting
    # convention as apps.core.dashboard_metrics.recent_messages.
    sender_name = serializers.SerializerMethodField()
    recipient_name = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "public_id", "sender", "sender_name", "recipient", "recipient_name",
            "subject", "body", "is_read", "read_at", "created_at",
        ]
        read_only_fields = ["is_read", "read_at", "created_at"]

    def get_sender_name(self, obj):
        return f"{obj.sender.first_name} {obj.sender.last_name}".strip() or obj.sender.email

    def get_recipient_name(self, obj):
        return f"{obj.recipient.first_name} {obj.recipient.last_name}".strip() or obj.recipient.email
