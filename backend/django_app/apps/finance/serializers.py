from rest_framework import serializers

from apps.core.serializers import PublicIdRelatedField
from apps.schools.models import AcademicYear, School, Term
from apps.students.models import Student

from .models import (
    Discount,
    FeeItem,
    FeeStructure,
    Invoice,
    InvoiceLine,
    LedgerEntry,
    Payment,
    Receipt,
    Refund,
    Scholarship,
)


class FeeStructureSerializer(serializers.ModelSerializer):
    term = PublicIdRelatedField(queryset=Term.objects)
    school = PublicIdRelatedField(read_only=True)
    academic_year = PublicIdRelatedField(read_only=True)

    class Meta:
        model = FeeStructure
        fields = ["public_id", "school", "academic_year", "term", "name", "is_active"]


class FeeItemSerializer(serializers.ModelSerializer):
    fee_structure = PublicIdRelatedField(queryset=FeeStructure.objects)

    class Meta:
        model = FeeItem
        fields = ["public_id", "fee_structure", "name", "amount_minor", "currency_code", "is_mandatory"]
        read_only_fields = ["currency_code"]


class DiscountSerializer(serializers.ModelSerializer):
    school = PublicIdRelatedField(queryset=School.objects)

    class Meta:
        model = Discount
        fields = [
            "public_id", "school", "name", "discount_type", "percentage", "fixed_amount_minor", "is_active",
        ]


class ScholarshipSerializer(serializers.ModelSerializer):
    student = PublicIdRelatedField(queryset=Student.objects)
    discount = PublicIdRelatedField(queryset=Discount.objects)
    academic_year = PublicIdRelatedField(queryset=AcademicYear.objects)

    class Meta:
        model = Scholarship
        fields = ["public_id", "student", "discount", "academic_year", "is_active"]


class InvoiceSerializer(serializers.ModelSerializer):
    student = PublicIdRelatedField(queryset=Student.objects)
    term = PublicIdRelatedField(queryset=Term.objects)
    school = PublicIdRelatedField(read_only=True)
    academic_year = PublicIdRelatedField(read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "public_id", "school", "student", "academic_year", "term", "invoice_number",
            "total_minor", "currency_code", "status", "due_date", "issued_at",
        ]
        read_only_fields = ["total_minor", "currency_code", "status", "issued_at"]
        validators = []


class InvoiceLineSerializer(serializers.ModelSerializer):
    invoice = PublicIdRelatedField(queryset=Invoice.objects)
    fee_item = PublicIdRelatedField(queryset=FeeItem.objects, required=False, allow_null=True)
    discount = PublicIdRelatedField(queryset=Discount.objects, required=False, allow_null=True)
    # Both derivable server-side from fee_item (see invoice_line_service.add_line)
    # when the caller bills a line straight off a FeeItem rather than a custom charge.
    description = serializers.CharField(required=False)
    unit_amount_minor = serializers.IntegerField(required=False)

    class Meta:
        model = InvoiceLine
        fields = [
            "public_id", "invoice", "fee_item", "description", "quantity", "unit_amount_minor",
            "discount", "discount_amount_minor", "amount_minor",
        ]
        read_only_fields = ["discount_amount_minor", "amount_minor"]


class PaymentSerializer(serializers.ModelSerializer):
    invoice = PublicIdRelatedField(queryset=Invoice.objects)

    class Meta:
        model = Payment
        fields = [
            "public_id", "invoice", "reference", "amount_minor", "currency_code", "method",
            "status", "paid_at",
        ]
        read_only_fields = ["currency_code", "status"]
        extra_kwargs = {"paid_at": {"required": False}}
        validators = []


class RefundSerializer(serializers.ModelSerializer):
    payment = PublicIdRelatedField(queryset=Payment.objects)

    class Meta:
        model = Refund
        fields = ["public_id", "payment", "amount_minor", "currency_code", "reason", "status", "processed_at"]
        read_only_fields = ["currency_code", "status", "processed_at"]


class ReceiptSerializer(serializers.ModelSerializer):
    payment = PublicIdRelatedField(read_only=True)

    class Meta:
        model = Receipt
        fields = [
            "public_id", "payment", "receipt_number", "status", "file_url", "generated_at", "error_message",
        ]


class LedgerEntrySerializer(serializers.ModelSerializer):
    school = PublicIdRelatedField(read_only=True)

    class Meta:
        model = LedgerEntry
        fields = [
            "public_id", "school", "account", "debit_minor", "credit_minor", "currency_code",
            "ref_type", "ref_id", "description", "created_at",
        ]
