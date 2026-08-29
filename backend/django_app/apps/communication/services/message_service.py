"""Thin views, fat services (§11 ARCHITECTURE.md). `sender` is always the
acting user — there's no notion of sending a message on someone else's
behalf, so it's derived from `actor` rather than being a separate param.
"""
from django.utils import timezone

from apps.communication.models import Message


def send_message(*, recipient, actor, subject: str = "", body: str) -> Message:
    return Message.objects.create(
        organization=actor.organization,
        sender=actor,
        recipient=recipient,
        subject=subject,
        body=body,
        created_by=actor,
        updated_by=actor,
    )


def mark_read(*, message: Message, actor) -> Message:
    message.is_read = True
    message.read_at = timezone.now()
    message.updated_by = actor
    message.save(update_fields=["is_read", "read_at", "updated_by", "updated_at"])
    return message
