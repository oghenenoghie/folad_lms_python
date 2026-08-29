"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.inventory.models import Supplier
from apps.schools.models import School


def create_supplier(*, school: School, actor, **fields) -> Supplier:
    return Supplier.objects.create(
        organization=school.organization, school=school, created_by=actor, updated_by=actor, **fields
    )


def update_supplier(*, supplier: Supplier, actor, **fields) -> Supplier:
    for field, value in fields.items():
        setattr(supplier, field, value)
    supplier.updated_by = actor
    supplier.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return supplier


def delete_supplier(*, supplier: Supplier, actor) -> None:
    supplier.deleted_at = timezone.now()
    supplier.updated_by = actor
    supplier.save(update_fields=["deleted_at", "updated_by", "updated_at"])
