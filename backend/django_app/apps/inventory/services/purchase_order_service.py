"""Thin views, fat services (§11 ARCHITECTURE.md). One item per purchase
order (models.py has no separate line-item model) — the catalogue (§6)
lists PurchaseOrder as its own entity with no line-item companion, and a
school ordering multiple items in one trip is adequately modeled as
multiple PurchaseOrder rows sharing an order date, so a line-item table
would be premature structure with no named requirement backing it.
"""
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import InventoryItem, PurchaseOrder, Supplier
from apps.inventory.services import stock_movement_service
from apps.inventory.services.exceptions import InvalidPurchaseOrderState


def create_purchase_order(*, supplier: Supplier, item: InventoryItem, actor, **fields) -> PurchaseOrder:
    fields.setdefault("currency_code", item.organization.currency_code)
    return PurchaseOrder.objects.create(
        organization=item.organization,
        school=item.school,
        supplier=supplier,
        item=item,
        created_by=actor,
        updated_by=actor,
        **fields,
    )


def update_purchase_order(*, purchase_order: PurchaseOrder, actor, **fields) -> PurchaseOrder:
    if purchase_order.status != "draft":
        raise InvalidPurchaseOrderState(f"cannot edit a purchase order once it is '{purchase_order.status}'")
    for field, value in fields.items():
        setattr(purchase_order, field, value)
    purchase_order.updated_by = actor
    purchase_order.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return purchase_order


def delete_purchase_order(*, purchase_order: PurchaseOrder, actor) -> None:
    if purchase_order.status != "draft":
        raise InvalidPurchaseOrderState(f"cannot delete a purchase order once it is '{purchase_order.status}'")
    purchase_order.deleted_at = timezone.now()
    purchase_order.updated_by = actor
    purchase_order.save(update_fields=["deleted_at", "updated_by", "updated_at"])


def mark_ordered(*, purchase_order: PurchaseOrder, actor) -> PurchaseOrder:
    if purchase_order.status != "draft":
        raise InvalidPurchaseOrderState(f"cannot order a purchase order that is already '{purchase_order.status}'")
    purchase_order.status = "ordered"
    purchase_order.ordered_at = timezone.now()
    purchase_order.updated_by = actor
    purchase_order.save(update_fields=["status", "ordered_at", "updated_by", "updated_at"])
    return purchase_order


def receive_purchase_order(*, purchase_order: PurchaseOrder, actor) -> PurchaseOrder:
    if purchase_order.status != "ordered":
        raise InvalidPurchaseOrderState(f"cannot receive a purchase order that is '{purchase_order.status}'")
    with transaction.atomic():
        stock_movement_service.record_movement(
            item=purchase_order.item,
            actor=actor,
            movement_type="in",
            quantity=purchase_order.quantity_ordered,
            ref_type="purchase_order",
            ref_id=purchase_order.id,
            note=f"Received against PO {purchase_order.order_number}",
        )
        purchase_order.status = "received"
        purchase_order.received_at = timezone.now()
        purchase_order.updated_by = actor
        purchase_order.save(update_fields=["status", "received_at", "updated_by", "updated_at"])
    return purchase_order


def cancel_purchase_order(*, purchase_order: PurchaseOrder, actor) -> PurchaseOrder:
    if purchase_order.status not in ("draft", "ordered"):
        raise InvalidPurchaseOrderState(f"cannot cancel a purchase order that is already '{purchase_order.status}'")
    purchase_order.status = "cancelled"
    purchase_order.updated_by = actor
    purchase_order.save(update_fields=["status", "updated_by", "updated_at"])
    return purchase_order
