"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.schools.models import Department, School


def create_department(*, school: School, actor, **fields) -> Department:
    return Department.objects.create(
        organization=school.organization, school=school, created_by=actor, updated_by=actor, **fields
    )


def update_department(*, department: Department, actor, **fields) -> Department:
    for field, value in fields.items():
        setattr(department, field, value)
    department.updated_by = actor
    department.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return department


def delete_department(*, department: Department, actor) -> None:
    department.deleted_at = timezone.now()
    department.updated_by = actor
    department.save(update_fields=["deleted_at", "updated_by", "updated_at"])
