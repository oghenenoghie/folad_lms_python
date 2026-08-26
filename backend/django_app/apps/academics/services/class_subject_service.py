"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.academics.models import ClassArm, ClassSubject, Subject
from apps.staff.models import Teacher


def create_class_subject(
    *, class_arm: ClassArm, subject: Subject, teacher: Teacher, actor, **fields
) -> ClassSubject:
    return ClassSubject.objects.create(
        organization=class_arm.organization,
        class_arm=class_arm,
        subject=subject,
        teacher=teacher,
        created_by=actor,
        updated_by=actor,
        **fields,
    )


def update_class_subject(*, class_subject: ClassSubject, actor, **fields) -> ClassSubject:
    for field, value in fields.items():
        setattr(class_subject, field, value)
    class_subject.updated_by = actor
    class_subject.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return class_subject


def delete_class_subject(*, class_subject: ClassSubject, actor) -> None:
    class_subject.deleted_at = timezone.now()
    class_subject.updated_by = actor
    class_subject.save(update_fields=["deleted_at", "updated_by", "updated_at"])
