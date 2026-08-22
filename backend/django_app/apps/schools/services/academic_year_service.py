"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.db import transaction
from django.utils import timezone

from apps.schools.models import AcademicYear, School


def create_academic_year(*, school: School, actor, **fields) -> AcademicYear:
    return AcademicYear.objects.create(
        organization=school.organization, school=school, created_by=actor, updated_by=actor, **fields
    )


def update_academic_year(*, academic_year: AcademicYear, actor, **fields) -> AcademicYear:
    for field, value in fields.items():
        setattr(academic_year, field, value)
    academic_year.updated_by = actor
    academic_year.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return academic_year


def delete_academic_year(*, academic_year: AcademicYear, actor) -> None:
    academic_year.deleted_at = timezone.now()
    academic_year.updated_by = actor
    academic_year.save(update_fields=["deleted_at", "updated_by", "updated_at"])


def activate_academic_year(*, academic_year: AcademicYear, actor) -> AcademicYear:
    """Marks `academic_year` as the school's current one, atomically unsetting
    whichever year previously held that flag (§9/§18: activation is a
    specialized update, not a distinct RBAC capability — see urls.py)."""
    with transaction.atomic():
        # select_for_update() locks the contended rows for the rest of this
        # transaction so a concurrent activate() can't race between the
        # unset-previous and set-new steps and leave two years both current.
        list(
            AcademicYear.objects.select_for_update()
            .filter(school_id=academic_year.school_id, is_current=True)
            .exclude(pk=academic_year.pk)
        )
        AcademicYear.objects.filter(
            school_id=academic_year.school_id, is_current=True
        ).exclude(pk=academic_year.pk).update(is_current=False, updated_by=actor, updated_at=timezone.now())
        academic_year.is_current = True
        academic_year.updated_by = actor
        academic_year.save(update_fields=["is_current", "updated_by", "updated_at"])
    return academic_year
