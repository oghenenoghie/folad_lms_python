from django.urls import path

from .views import (
    AnnouncementDetailView,
    AnnouncementListCreateView,
    AnnouncementPublishView,
    MessageListCreateView,
    MessageMarkReadView,
    NotificationListView,
    NotificationMarkAllReadView,
    NotificationMarkReadView,
    NotificationPreferenceView,
)

urlpatterns = [
    path("announcements", AnnouncementListCreateView.as_view(), name="announcement-list-create"),
    path("announcements/<uuid:public_id>", AnnouncementDetailView.as_view(), name="announcement-detail"),
    path(
        "announcements/<uuid:public_id>/publish",
        AnnouncementPublishView.as_view(),
        name="announcement-publish",
    ),
    path("notifications", NotificationListView.as_view(), name="notification-list"),
    path(
        "notifications/<uuid:public_id>/read",
        NotificationMarkReadView.as_view(),
        name="notification-mark-read",
    ),
    path(
        "notifications/mark-all-read",
        NotificationMarkAllReadView.as_view(),
        name="notification-mark-all-read",
    ),
    path("notification-preferences", NotificationPreferenceView.as_view(), name="notification-preferences"),
    path("messages", MessageListCreateView.as_view(), name="message-list-create"),
    path("messages/<uuid:public_id>/read", MessageMarkReadView.as_view(), name="message-mark-read"),
]
