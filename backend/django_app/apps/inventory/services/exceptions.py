"""Domain errors — surfaced by views.py as a 409."""


class InventoryError(Exception):
    pass


class InsufficientStock(InventoryError):
    pass


class InvalidPurchaseOrderState(InventoryError):
    pass
