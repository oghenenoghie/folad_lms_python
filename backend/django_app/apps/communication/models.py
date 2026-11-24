"""§4/§6/§18 ARCHITECTURE.md (Milestone 10). Announcement is school-wide
broadcast content; publishing one fans out a Notification to every User in
its audience (see services/announcement_service.py) — the concrete case
this milestone's "notification center" exit criterion is built and tested
against, rather than retrofitting a Notification-emitting hook into every
other app's already-merged workflows. Message is a direct, one-to-one
exchange between two platform users (not run through Notification — a
Message *is* the content, not a pointer to it elsewhere). Every model
denormalizes `organization` directly, same convention as every other app.
"""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.tenancy.managers import TenantManager

ANNOUNCEMENT_AUDIENCE_CHOICES = [
    ("all", "All"),
    ("students", "Students"),
    ("staff", "Staff"),
    ("parents", "Parents"),
]

NOTIFICATION_TYPE_CHOICES = [
    ("announcement", "Announcement"),
    ("system", "System"),
]


class Announcement(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="announcements")
    title = models.CharField(max_length=200)
    body = models.TextField()
    audience = models.CharField(max_length=20, choices=ANNOUNCEMENT_AUDIENCE_CHOICES, default="all")
    is_pinned = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "communication_announcement"
        ordering = ["-is_pinned", "-created_at"]

    def __str__(self) -> str:
        return self.title


class Notification(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, default="")
    link_url = models.CharField(max_length=500, blank=True, default="")
    ref_type = models.CharField(max_length=20, blank=True, default="")
    ref_id = models.BigIntegerField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "communication_notification"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.recipient}: {self.title}"


class NotificationPreference(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preference"
    )
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    push_enabled = models.BooleanField(default=True)
    in_app_enabled = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "communication_notification_preference"

    def __str__(self) -> str:
        return f"Preferences for {self.user}"


class Message(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sent_messages"
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="received_messages"
    )
    subject = models.CharField(max_length=200, blank=True, default="")
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "communication_message"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.sender} -> {self.recipient}: {self.subject}"
