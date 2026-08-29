"""Thin views, fat services (§11 ARCHITECTURE.md). No client-facing update to
`quantity_on_hand` here — see the models.py module docstring: it only ever
changes via stock_movement_service.record_movement."""
from django.utils import timezone

from apps.inventory.models import InventoryItem
from apps.schools.models import School


def create_item(*, school: School, actor, **fields) -> InventoryItem:
    fields.pop("quantity_on_hand", None)
    return InventoryItem.objects.create(
        organization=school.organization, school=school, created_by=actor, updated_by=actor, **fields
    )


def update_item(*, item: InventoryItem, actor, **fields) -> InventoryItem:
    fields.pop("quantity_on_hand", None)
    for field, value in fields.items():
        setattr(item, field, value)
    item.updated_by = actor
    item.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return item


def delete_item(*, item: InventoryItem, actor) -> None:
    item.deleted_at = timezone.now()
    item.updated_by = actor
    item.save(update_fields=["deleted_at", "updated_by", "updated_at"])
