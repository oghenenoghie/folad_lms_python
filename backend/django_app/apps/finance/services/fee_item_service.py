"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.finance.models import FeeItem, FeeStructure


def create_fee_item(*, fee_structure: FeeStructure, actor, **fields) -> FeeItem:
    fields.setdefault("currency_code", fee_structure.organization.currency_code)
    return FeeItem.objects.create(
        organization=fee_structure.organization,
        fee_structure=fee_structure,
        created_by=actor,
        updated_by=actor,
        **fields,
    )


def update_fee_item(*, fee_item: FeeItem, actor, **fields) -> FeeItem:
    for field, value in fields.items():
        setattr(fee_item, field, value)
    fee_item.updated_by = actor
    fee_item.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return fee_item


def delete_fee_item(*, fee_item: FeeItem, actor) -> None:
    fee_item.deleted_at = timezone.now()
    fee_item.updated_by = actor
    fee_item.save(update_fields=["deleted_at", "updated_by", "updated_at"])
