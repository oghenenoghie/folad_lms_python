from django.urls import path

from .views import (
    InventoryItemDetailView,
    InventoryItemListCreateView,
    PurchaseOrderCancelView,
    PurchaseOrderDetailView,
    PurchaseOrderListCreateView,
    PurchaseOrderMarkOrderedView,
    PurchaseOrderReceiveView,
    StockMovementListCreateView,
    SupplierDetailView,
    SupplierListCreateView,
)

urlpatterns = [
    path("inventory-items", InventoryItemListCreateView.as_view(), name="inventory-item-list-create"),
    path(
        "inventory-items/<uuid:public_id>", InventoryItemDetailView.as_view(), name="inventory-item-detail"
    ),
    path("suppliers", SupplierListCreateView.as_view(), name="supplier-list-create"),
    path("suppliers/<uuid:public_id>", SupplierDetailView.as_view(), name="supplier-detail"),
    path("purchase-orders", PurchaseOrderListCreateView.as_view(), name="purchase-order-list-create"),
    path(
        "purchase-orders/<uuid:public_id>", PurchaseOrderDetailView.as_view(), name="purchase-order-detail"
    ),
    path(
        "purchase-orders/<uuid:public_id>/mark-ordered",
        PurchaseOrderMarkOrderedView.as_view(),
        name="purchase-order-mark-ordered",
    ),
    path(
        "purchase-orders/<uuid:public_id>/receive",
        PurchaseOrderReceiveView.as_view(),
        name="purchase-order-receive",
    ),
    path(
        "purchase-orders/<uuid:public_id>/cancel",
        PurchaseOrderCancelView.as_view(),
        name="purchase-order-cancel",
    ),
    path("stock-movements", StockMovementListCreateView.as_view(), name="stock-movement-list-create"),
]
