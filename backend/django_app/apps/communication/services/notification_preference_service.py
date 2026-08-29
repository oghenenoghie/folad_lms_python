"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from apps.communication.models import NotificationPreference


def get_or_create_preference(*, user, actor) -> NotificationPreference:
    preference, _ = NotificationPreference.objects.get_or_create(
        user=user, defaults={"organization": user.organization, "created_by": actor, "updated_by": actor}
    )
    return preference


def update_preference(*, preference: NotificationPreference, actor, **fields) -> NotificationPreference:
    for field, value in fields.items():
        setattr(preference, field, value)
    preference.updated_by = actor
    preference.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return preference
