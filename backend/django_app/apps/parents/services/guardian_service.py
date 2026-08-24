"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.parents.models import Guardian


def create_guardian(*, organization, actor, **fields) -> Guardian:
    return Guardian.objects.create(
        organization=organization, created_by=actor, updated_by=actor, **fields
    )


def update_guardian(*, guardian: Guardian, actor, **fields) -> Guardian:
    for field, value in fields.items():
        setattr(guardian, field, value)
    guardian.updated_by = actor
    guardian.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return guardian


def delete_guardian(*, guardian: Guardian, actor) -> None:
    guardian.deleted_at = timezone.now()
    guardian.updated_by = actor
    guardian.save(update_fields=["deleted_at", "updated_by", "updated_at"])
