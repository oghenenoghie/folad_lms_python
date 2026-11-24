"""Thin views, fat services (§11 ARCHITECTURE.md). PurchaseOrder gets
dedicated order/receive/cancel transition endpoints (mirroring
apps.examinations' Result), since receiving one is what actually posts a
StockMovement and moves real stock — not something a generic PATCH should
do quietly. StockMovement is create + read-only and append-only at the DB
layer (see models.py) — no client-facing update or delete anywhere.
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import require_permission
from apps.core.generics import TenantListCreateAPIView, TenantRetrieveUpdateDestroyAPIView
from apps.core.responses import envelope, error_envelope

from .models import InventoryItem, PurchaseOrder, StockMovement, Supplier
from .serializers import (
    InventoryItemSerializer,
    PurchaseOrderSerializer,
    StockMovementSerializer,
    SupplierSerializer,
)
from .services import item_service, purchase_order_service, stock_movement_service, supplier_service
from .services.exceptions import InventoryError


class InventoryItemListCreateView(TenantListCreateAPIView):
    serializer_class = InventoryItemSerializer

    def get_queryset(self):
        qs = InventoryItem.objects.filter(deleted_at__isnull=True)
        school_id = self.request.query_params.get("school_id")
        if school_id:
            qs = qs.filter(school__public_id=school_id)
        return qs

    def get_permissions(self):
        code = "inventory_items.create" if self.request.method == "POST" else "inventory_items.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        school = data.pop("school")
        serializer.instance = item_service.create_item(school=school, actor=self.request.user, **data)


class InventoryItemDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = InventoryItemSerializer

    def get_queryset(self):
        return InventoryItem.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "inventory_items.view",
            "PATCH": "inventory_items.update",
            "DELETE": "inventory_items.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("school", None)
        item_service.update_item(item=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        item_service.delete_item(item=instance, actor=self.request.user)


class SupplierListCreateView(TenantListCreateAPIView):
    serializer_class = SupplierSerializer

    def get_queryset(self):
        qs = Supplier.objects.filter(deleted_at__isnull=True)
        school_id = self.request.query_params.get("school_id")
        if school_id:
            qs = qs.filter(school__public_id=school_id)
        return qs

    def get_permissions(self):
        code = "suppliers.create" if self.request.method == "POST" else "suppliers.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        school = data.pop("school")
        serializer.instance = supplier_service.create_supplier(school=school, actor=self.request.user, **data)


class SupplierDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = SupplierSerializer

    def get_queryset(self):
        return Supplier.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "suppliers.view", "PATCH": "suppliers.update", "DELETE": "suppliers.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("school", None)
        supplier_service.update_supplier(supplier=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        supplier_service.delete_supplier(supplier=instance, actor=self.request.user)


class PurchaseOrderListCreateView(TenantListCreateAPIView):
    serializer_class = PurchaseOrderSerializer

    def get_queryset(self):
        qs = PurchaseOrder.objects.filter(deleted_at__isnull=True)
        item_id = self.request.query_params.get("item_id")
        status_param = self.request.query_params.get("status")
        if item_id:
            qs = qs.filter(item__public_id=item_id)
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def get_permissions(self):
        code = "purchase_orders.create" if self.request.method == "POST" else "purchase_orders.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        supplier = data.pop("supplier")
        item = data.pop("item")
        serializer.instance = purchase_order_service.create_purchase_order(
            supplier=supplier, item=item, actor=self.request.user, **data
        )


class PurchaseOrderDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = PurchaseOrderSerializer

    def get_queryset(self):
        return PurchaseOrder.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "purchase_orders.view",
            "PATCH": "purchase_orders.update",
            "DELETE": "purchase_orders.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except InventoryError as exc:
            return error_envelope(str(exc), status=409)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except InventoryError as exc:
            return error_envelope(str(exc), status=409)

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("supplier", None)
        data.pop("item", None)
        purchase_order_service.update_purchase_order(
            purchase_order=serializer.instance, actor=self.request.user, **data
        )

    def perform_destroy(self, instance):
        purchase_order_service.delete_purchase_order(purchase_order=instance, actor=self.request.user)


class _PurchaseOrderTransitionView(APIView):
    permission_code = None

    def get_permissions(self):
        return [IsAuthenticated(), require_permission(self.permission_code)()]

    def post(self, request, public_id):
        try:
            purchase_order = PurchaseOrder.objects.filter(deleted_at__isnull=True).get(public_id=public_id)
        except PurchaseOrder.DoesNotExist:
            return error_envelope("purchase order not found", status=404)
        try:
            self.transition(purchase_order=purchase_order, actor=request.user)
        except InventoryError as exc:
            return error_envelope(str(exc), status=409)
        return envelope(PurchaseOrderSerializer(purchase_order).data, message=f"purchase order {purchase_order.status}")

    def transition(self, *, purchase_order, actor):
        raise NotImplementedError


class PurchaseOrderMarkOrderedView(_PurchaseOrderTransitionView):
    permission_code = "purchase_orders.update"

    def transition(self, *, purchase_order, actor):
        purchase_order_service.mark_ordered(purchase_order=purchase_order, actor=actor)


class PurchaseOrderReceiveView(_PurchaseOrderTransitionView):
    permission_code = "purchase_orders.receive"

    def transition(self, *, purchase_order, actor):
        purchase_order_service.receive_purchase_order(purchase_order=purchase_order, actor=actor)


class PurchaseOrderCancelView(_PurchaseOrderTransitionView):
    permission_code = "purchase_orders.update"

    def transition(self, *, purchase_order, actor):
        purchase_order_service.cancel_purchase_order(purchase_order=purchase_order, actor=actor)


class StockMovementListCreateView(TenantListCreateAPIView):
    serializer_class = StockMovementSerializer

    def get_queryset(self):
        qs = StockMovement.objects.all()
        item_id = self.request.query_params.get("item_id")
        if item_id:
            qs = qs.filter(item__public_id=item_id)
        return qs

    def get_permissions(self):
        code = "stock_movements.create" if self.request.method == "POST" else "stock_movements.view"
        return [IsAuthenticated(), require_permission(code)()]

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except InventoryError as exc:
            return error_envelope(str(exc), status=409)

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        item = data.pop("item")
        serializer.instance = stock_movement_service.record_movement(
            item=item, actor=self.request.user, **data
        )
