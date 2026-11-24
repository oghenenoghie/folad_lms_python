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

    class Meta:
        model = Message
        fields = ["public_id", "sender", "recipient", "subject", "body", "is_read", "read_at", "created_at"]
        read_only_fields = ["is_read", "read_at", "created_at"]
