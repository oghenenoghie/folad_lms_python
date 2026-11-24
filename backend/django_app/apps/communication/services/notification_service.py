"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.communication.models import Notification


def mark_read(*, notification: Notification, actor) -> Notification:
    notification.is_read = True
    notification.read_at = timezone.now()
    notification.updated_by = actor
    notification.save(update_fields=["is_read", "read_at", "updated_by", "updated_at"])
    return notification


def mark_all_read(*, user, actor) -> int:
    return Notification.objects.filter(recipient=user, is_read=False).update(
        is_read=True, read_at=timezone.now(), updated_by=actor, updated_at=timezone.now()
    )
