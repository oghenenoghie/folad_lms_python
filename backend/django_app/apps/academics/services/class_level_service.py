"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.academics.models import ClassLevel
from apps.schools.models import Campus


def create_class_level(*, campus: Campus, actor, **fields) -> ClassLevel:
    return ClassLevel.objects.create(
        organization=campus.organization, campus=campus, created_by=actor, updated_by=actor, **fields
    )


def update_class_level(*, class_level: ClassLevel, actor, **fields) -> ClassLevel:
    for field, value in fields.items():
        setattr(class_level, field, value)
    class_level.updated_by = actor
    class_level.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return class_level


def delete_class_level(*, class_level: ClassLevel, actor) -> None:
    class_level.deleted_at = timezone.now()
    class_level.updated_by = actor
    class_level.save(update_fields=["deleted_at", "updated_by", "updated_at"])
