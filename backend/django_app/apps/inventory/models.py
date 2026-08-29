"""§6/§18/§19 ARCHITECTURE.md (Milestone 9). "Stock-movement accuracy" is
§19's named risk for this module: InventoryItem.quantity_on_hand is never
written directly by a client — every change is a StockMovement row (in/out/
adjustment), and the item's running total is only ever derived by applying
them, same current-state-plus-immutable-history split as LedgerEntry is to
Invoice/Payment/Refund, right down to being append-only via the same DB
trigger. PurchaseOrder orders one InventoryItem at a time (no separate line-
item model — see the module docstring in services/purchase_order_service.py
for why); receiving it posts the StockMovement that actually moves stock.
Every model denormalizes `organization` directly, same convention as every
other app.
"""
from django.db import models

from apps.core.models import BaseModel
from apps.tenancy.managers import TenantManager

PURCHASE_ORDER_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("ordered", "Ordered"),
    ("received", "Received"),
    ("cancelled", "Cancelled"),
]

STOCK_MOVEMENT_TYPE_CHOICES = [
    ("in", "In"),
    ("out", "Out"),
    ("adjustment", "Adjustment"),
]


class InventoryItem(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="inventory_items")
    name = models.CharField(max_length=150)
    sku = models.CharField(max_length=50)
    category = models.CharField(max_length=100, blank=True, default="")
    quantity_on_hand = models.IntegerField(default=0)
    reorder_level = models.IntegerField(default=0)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "inventory_item"
        constraints = [
            models.UniqueConstraint(fields=["school", "sku"], name="uq_inventory_item_school_sku")
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Supplier(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="suppliers")
    name = models.CharField(max_length=150)
    contact_email = models.EmailField(blank=True, default="")
    contact_phone = models.CharField(max_length=32, blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "inventory_supplier"
        constraints = [
            models.UniqueConstraint(fields=["school", "name"], name="uq_supplier_school_name")
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class PurchaseOrder(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="purchase_orders")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_orders")
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="purchase_orders")
    order_number = models.CharField(max_length=40)
    quantity_ordered = models.PositiveIntegerField()
    unit_cost_minor = models.BigIntegerField()
    currency_code = models.CharField(max_length=3)
    status = models.CharField(max_length=20, choices=PURCHASE_ORDER_STATUS_CHOICES, default="draft")
    ordered_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "inventory_purchase_order"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "order_number"], name="uq_purchase_order_school_number"
            )
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.order_number


class StockMovement(BaseModel):
    """Append-only: see the module docstring. Only ever inserted, never
    updated or soft-deleted — a correction is a new offsetting movement,
    not an edit."""

    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="movements")
    # "in"/"out"/"adjustment" is a display/filter category; the actual signed
    # delta applied to quantity_on_hand is `quantity` itself (negative for a
    # decrease) — see services/stock_movement_service.py.
    movement_type = models.CharField(max_length=20, choices=STOCK_MOVEMENT_TYPE_CHOICES)
    quantity = models.IntegerField()
    ref_type = models.CharField(max_length=20, blank=True, default="")
    ref_id = models.BigIntegerField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True, default="")
    occurred_at = models.DateTimeField()

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "inventory_stock_movement"
        ordering = ["-occurred_at"]
        indexes = [models.Index(fields=["ref_type", "ref_id"])]

    def __str__(self) -> str:
        return f"{self.item}: {self.movement_type} {self.quantity}"
