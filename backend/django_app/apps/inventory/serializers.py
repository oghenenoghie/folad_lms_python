from rest_framework import serializers

from apps.core.serializers import PublicIdRelatedField
from apps.schools.models import School

from .models import InventoryItem, PurchaseOrder, StockMovement, Supplier


class InventoryItemSerializer(serializers.ModelSerializer):
    school = PublicIdRelatedField(queryset=School.objects)

    class Meta:
        model = InventoryItem
        fields = ["public_id", "school", "name", "sku", "category", "quantity_on_hand", "reorder_level"]
        read_only_fields = ["quantity_on_hand"]


class SupplierSerializer(serializers.ModelSerializer):
    school = PublicIdRelatedField(queryset=School.objects)

    class Meta:
        model = Supplier
        fields = ["public_id", "school", "name", "contact_email", "contact_phone", "address"]


class PurchaseOrderSerializer(serializers.ModelSerializer):
    supplier = PublicIdRelatedField(queryset=Supplier.objects)
    item = PublicIdRelatedField(queryset=InventoryItem.objects)
    school = PublicIdRelatedField(read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            "public_id", "school", "supplier", "item", "order_number", "quantity_ordered",
            "unit_cost_minor", "currency_code", "status", "ordered_at", "received_at",
        ]
        read_only_fields = ["order_number", "currency_code", "status", "ordered_at", "received_at"]


class StockMovementSerializer(serializers.ModelSerializer):
    item = PublicIdRelatedField(queryset=InventoryItem.objects)

    class Meta:
        model = StockMovement
        fields = [
            "public_id", "item", "movement_type", "quantity", "ref_type", "ref_id", "note", "occurred_at",
        ]
        extra_kwargs = {"occurred_at": {"required": False}}
