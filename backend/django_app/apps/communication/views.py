"""Thin views, fat services (§11 ARCHITECTURE.md). Notification is read +
mark-read only — never created directly by a client (see
announcement_service.publish_announcement, the only place they're written).
Every list here is implicitly scoped to the requesting user (recipient=
request.user / sender-or-recipient=request.user) on top of tenant scoping —
a user's own notifications/messages, not the whole organization's.
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import require_permission
from apps.core.generics import TenantListAPIView, TenantListCreateAPIView, TenantRetrieveUpdateDestroyAPIView
from apps.core.responses import envelope, error_envelope

from .models import Announcement, Message, Notification
from .serializers import (
    AnnouncementSerializer,
    MessageSerializer,
    NotificationPreferenceSerializer,
    NotificationSerializer,
)
from .services import announcement_service, message_service, notification_preference_service, notification_service


class AnnouncementListCreateView(TenantListCreateAPIView):
    serializer_class = AnnouncementSerializer

    def get_queryset(self):
        qs = Announcement.objects.filter(deleted_at__isnull=True)
        school_id = self.request.query_params.get("school_id")
        if school_id:
            qs = qs.filter(school__public_id=school_id)
        return qs

    def get_permissions(self):
        code = "announcements.create" if self.request.method == "POST" else "announcements.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        school = data.pop("school")
        serializer.instance = announcement_service.create_announcement(
            school=school, actor=self.request.user, **data
        )


class AnnouncementDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = AnnouncementSerializer

    def get_queryset(self):
        return Announcement.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "announcements.view",
            "PATCH": "announcements.update",
            "DELETE": "announcements.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("school", None)
        announcement_service.update_announcement(
            announcement=serializer.instance, actor=self.request.user, **data
        )

    def perform_destroy(self, instance):
        announcement_service.delete_announcement(announcement=instance, actor=self.request.user)


class AnnouncementPublishView(APIView):
    permission_classes = [IsAuthenticated, require_permission("announcements.update")]

    def post(self, request, public_id):
        try:
            announcement = Announcement.objects.filter(deleted_at__isnull=True).get(public_id=public_id)
        except Announcement.DoesNotExist:
            return error_envelope("announcement not found", status=404)
        announcement = announcement_service.publish_announcement(announcement=announcement, actor=request.user)
        return envelope(AnnouncementSerializer(announcement).data, message="announcement published")


class NotificationListView(TenantListAPIView):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user)
        is_read = self.request.query_params.get("is_read")
        if is_read is not None:
            qs = qs.filter(is_read=is_read.lower() == "true")
        return qs

    def get_permissions(self):
        return [IsAuthenticated()]


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, public_id):
        try:
            notification = Notification.objects.get(public_id=public_id, recipient=request.user)
        except Notification.DoesNotExist:
            return error_envelope("notification not found", status=404)
        notification = notification_service.mark_read(notification=notification, actor=request.user)
        return envelope(NotificationSerializer(notification).data, message="notification marked read")


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        count = notification_service.mark_all_read(user=request.user, actor=request.user)
        return envelope({"marked_read": count}, message="notifications marked read")


class NotificationPreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        preference = notification_preference_service.get_or_create_preference(
            user=request.user, actor=request.user
        )
        return envelope(NotificationPreferenceSerializer(preference).data)

    def patch(self, request):
        preference = notification_preference_service.get_or_create_preference(
            user=request.user, actor=request.user
        )
        serializer = NotificationPreferenceSerializer(preference, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        preference = notification_preference_service.update_preference(
            preference=preference, actor=request.user, **data
        )
        return envelope(NotificationPreferenceSerializer(preference).data, message="preferences updated")


class MessageListCreateView(TenantListCreateAPIView):
    serializer_class = MessageSerializer

    def get_queryset(self):
        from django.db.models import Q

        return Message.objects.filter(Q(sender=self.request.user) | Q(recipient=self.request.user))

    def get_permissions(self):
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        recipient = data.pop("recipient")
        serializer.instance = message_service.send_message(
            recipient=recipient, actor=self.request.user, **data
        )


class MessageMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, public_id):
        try:
            message = Message.objects.get(public_id=public_id, recipient=request.user)
        except Message.DoesNotExist:
            return error_envelope("message not found", status=404)
        message = message_service.mark_read(message=message, actor=request.user)
        return envelope(MessageSerializer(message).data, message="message marked read")
