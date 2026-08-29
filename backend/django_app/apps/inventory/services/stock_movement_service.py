"""Thin views, fat services (§11 ARCHITECTURE.md). The only path that ever
changes InventoryItem.quantity_on_hand — see the models.py module docstring.
select_for_update() on the item row serializes concurrent movements so two
racing "out" movements can't together overdraw stock. `quantity` carries its
own sign (positive = increase, negative = decrease); `movement_type` is a
display/filter category, cross-checked against that sign here so "in" can
never sneak in a decrease or vice versa.
"""
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import InventoryItem, StockMovement
from apps.inventory.services.exceptions import InsufficientStock, InventoryError

_EXPECTED_SIGN = {"in": 1, "out": -1}


def record_movement(
    *, item: InventoryItem, actor, movement_type: str, quantity: int,
    ref_type: str = "", ref_id: int | None = None, note: str = "", occurred_at=None,
) -> StockMovement:
    expected_sign = _EXPECTED_SIGN.get(movement_type)
    if expected_sign is not None and (quantity == 0 or (quantity > 0) != (expected_sign > 0)):
        raise InventoryError(f"a '{movement_type}' movement's quantity must be {'positive' if expected_sign > 0 else 'negative'}")

    with transaction.atomic():
        item = InventoryItem.objects.select_for_update().get(pk=item.pk)
        new_quantity = item.quantity_on_hand + quantity
        if new_quantity < 0:
            raise InsufficientStock(
                f"movement would take {item.name} to {new_quantity} (has {item.quantity_on_hand})"
            )
        movement = StockMovement.objects.create(
            organization=item.organization,
            item=item,
            movement_type=movement_type,
            quantity=quantity,
            ref_type=ref_type,
            ref_id=ref_id,
            note=note,
            occurred_at=occurred_at or timezone.now(),
            created_by=actor,
            updated_by=actor,
        )
        item.quantity_on_hand = new_quantity
        item.updated_by = actor
        item.save(update_fields=["quantity_on_hand", "updated_by", "updated_at"])
    return movement
