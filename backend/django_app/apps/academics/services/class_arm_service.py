"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.academics.models import ClassArm, ClassLevel


def create_class_arm(*, class_level: ClassLevel, actor, **fields) -> ClassArm:
    return ClassArm.objects.create(
        organization=class_level.organization,
        class_level=class_level,
        created_by=actor,
        updated_by=actor,
        **fields,
    )


def update_class_arm(*, class_arm: ClassArm, actor, **fields) -> ClassArm:
    for field, value in fields.items():
        setattr(class_arm, field, value)
    class_arm.updated_by = actor
    class_arm.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return class_arm


def delete_class_arm(*, class_arm: ClassArm, actor) -> None:
    class_arm.deleted_at = timezone.now()
    class_arm.updated_by = actor
    class_arm.save(update_fields=["deleted_at", "updated_by", "updated_at"])
