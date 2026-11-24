"""Thin views, fat services (§11 ARCHITECTURE.md). Invoice issue/cancel are
dedicated APIView endpoints, mirroring apps.schools' AcademicYearActivateView
and apps.examinations' Result transition views. Every endpoint whose service
can raise a finance.services.exceptions.FinanceError (an invalid state
transition or an amount outside what's allowed) catches it here and returns
a 409 rather than letting it surface as an unhandled 500. Payment and Refund
are create + read-only: once posted, a correction is a new Refund, never an
edit or delete of the original row (§18's "refunds as reversals").
LedgerEntry and Receipt are read-only everywhere — both are written only by
the services/tasks above, never directly by a client.
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import require_permission
from apps.core.generics import (
    TenantListAPIView,
    TenantListCreateAPIView,
    TenantRetrieveAPIView,
    TenantRetrieveUpdateDestroyAPIView,
)
from apps.core.responses import envelope, error_envelope

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
from .serializers import (
    DiscountSerializer,
    FeeItemSerializer,
    FeeStructureSerializer,
    InvoiceLineSerializer,
    InvoiceSerializer,
    LedgerEntrySerializer,
    PaymentSerializer,
    ReceiptSerializer,
    RefundSerializer,
    ScholarshipSerializer,
)
from .services import (
    discount_service,
    fee_item_service,
    fee_structure_service,
    invoice_line_service,
    invoice_service,
    payment_service,
    refund_service,
    scholarship_service,
)
from .services.exceptions import FinanceError


class FeeStructureListCreateView(TenantListCreateAPIView):
    serializer_class = FeeStructureSerializer

    def get_queryset(self):
        qs = FeeStructure.objects.filter(deleted_at__isnull=True)
        term_id = self.request.query_params.get("term_id")
        if term_id:
            qs = qs.filter(term__public_id=term_id)
        return qs

    def get_permissions(self):
        code = "fee_structures.create" if self.request.method == "POST" else "fee_structures.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        term = data.pop("term")
        serializer.instance = fee_structure_service.create_fee_structure(
            term=term, actor=self.request.user, **data
        )


class FeeStructureDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = FeeStructureSerializer

    def get_queryset(self):
        return FeeStructure.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "fee_structures.view",
            "PATCH": "fee_structures.update",
            "DELETE": "fee_structures.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("term", None)
        fee_structure_service.update_fee_structure(
            fee_structure=serializer.instance, actor=self.request.user, **data
        )

    def perform_destroy(self, instance):
        fee_structure_service.delete_fee_structure(fee_structure=instance, actor=self.request.user)


class FeeItemListCreateView(TenantListCreateAPIView):
    serializer_class = FeeItemSerializer

    def get_queryset(self):
        qs = FeeItem.objects.filter(deleted_at__isnull=True)
        fee_structure_id = self.request.query_params.get("fee_structure_id")
        if fee_structure_id:
            qs = qs.filter(fee_structure__public_id=fee_structure_id)
        return qs

    def get_permissions(self):
        code = "fee_items.create" if self.request.method == "POST" else "fee_items.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        fee_structure = data.pop("fee_structure")
        serializer.instance = fee_item_service.create_fee_item(
            fee_structure=fee_structure, actor=self.request.user, **data
        )


class FeeItemDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = FeeItemSerializer

    def get_queryset(self):
        return FeeItem.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "fee_items.view", "PATCH": "fee_items.update", "DELETE": "fee_items.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("fee_structure", None)
        fee_item_service.update_fee_item(fee_item=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        fee_item_service.delete_fee_item(fee_item=instance, actor=self.request.user)


class DiscountListCreateView(TenantListCreateAPIView):
    serializer_class = DiscountSerializer

    def get_queryset(self):
        qs = Discount.objects.filter(deleted_at__isnull=True)
        school_id = self.request.query_params.get("school_id")
        if school_id:
            qs = qs.filter(school__public_id=school_id)
        return qs

    def get_permissions(self):
        code = "discounts.create" if self.request.method == "POST" else "discounts.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        school = data.pop("school")
        serializer.instance = discount_service.create_discount(
            school=school, actor=self.request.user, **data
        )


class DiscountDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = DiscountSerializer

    def get_queryset(self):
        return Discount.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "discounts.view", "PATCH": "discounts.update", "DELETE": "discounts.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("school", None)
        discount_service.update_discount(discount=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        discount_service.delete_discount(discount=instance, actor=self.request.user)


class ScholarshipListCreateView(TenantListCreateAPIView):
    serializer_class = ScholarshipSerializer

    def get_queryset(self):
        qs = Scholarship.objects.filter(deleted_at__isnull=True)
        student_id = self.request.query_params.get("student_id")
        academic_year_id = self.request.query_params.get("academic_year_id")
        if student_id:
            qs = qs.filter(student__public_id=student_id)
        if academic_year_id:
            qs = qs.filter(academic_year__public_id=academic_year_id)
        return qs

    def get_permissions(self):
        code = "scholarships.create" if self.request.method == "POST" else "scholarships.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        student = data.pop("student")
        discount = data.pop("discount")
        academic_year = data.pop("academic_year")
        serializer.instance = scholarship_service.award_scholarship(
            student=student, discount=discount, academic_year=academic_year, actor=self.request.user, **data
        )


class ScholarshipDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = ScholarshipSerializer

    def get_queryset(self):
        return Scholarship.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "scholarships.view",
            "PATCH": "scholarships.update",
            "DELETE": "scholarships.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("student", None)
        data.pop("discount", None)
        data.pop("academic_year", None)
        scholarship_service.update_scholarship(
            scholarship=serializer.instance, actor=self.request.user, **data
        )

    def perform_destroy(self, instance):
        scholarship_service.revoke_scholarship(scholarship=instance, actor=self.request.user)


class InvoiceListCreateView(TenantListCreateAPIView):
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        qs = Invoice.objects.filter(deleted_at__isnull=True)
        student_id = self.request.query_params.get("student_id")
        term_id = self.request.query_params.get("term_id")
        status_param = self.request.query_params.get("status")
        if student_id:
            qs = qs.filter(student__public_id=student_id)
        if term_id:
            qs = qs.filter(term__public_id=term_id)
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def get_permissions(self):
        code = "invoices.create" if self.request.method == "POST" else "invoices.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        student = data.pop("student")
        term = data.pop("term")
        serializer.instance = invoice_service.create_invoice(
            student=student, term=term, actor=self.request.user, **data
        )


class InvoiceDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        return Invoice.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "invoices.view", "PATCH": "invoices.update", "DELETE": "invoices.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except FinanceError as exc:
            return error_envelope(str(exc), status=409)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except FinanceError as exc:
            return error_envelope(str(exc), status=409)

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("student", None)
        data.pop("term", None)
        invoice_service.update_invoice(invoice=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        invoice_service.delete_invoice(invoice=instance, actor=self.request.user)


class InvoiceIssueView(APIView):
    permission_classes = [IsAuthenticated, require_permission("invoices.issue")]

    def post(self, request, public_id):
        try:
            invoice = Invoice.objects.filter(deleted_at__isnull=True).get(public_id=public_id)
        except Invoice.DoesNotExist:
            return error_envelope("invoice not found", status=404)
        try:
            invoice_service.issue_invoice(invoice=invoice, actor=request.user)
        except FinanceError as exc:
            return error_envelope(str(exc), status=409)
        return envelope(InvoiceSerializer(invoice).data, message="invoice issued")


class InvoiceCancelView(APIView):
    permission_classes = [IsAuthenticated, require_permission("invoices.cancel")]

    def post(self, request, public_id):
        try:
            invoice = Invoice.objects.filter(deleted_at__isnull=True).get(public_id=public_id)
        except Invoice.DoesNotExist:
            return error_envelope("invoice not found", status=404)
        try:
            invoice_service.cancel_invoice(invoice=invoice, actor=request.user)
        except FinanceError as exc:
            return error_envelope(str(exc), status=409)
        return envelope(InvoiceSerializer(invoice).data, message="invoice cancelled")


class InvoiceLineListCreateView(TenantListCreateAPIView):
    serializer_class = InvoiceLineSerializer

    def get_queryset(self):
        qs = InvoiceLine.objects.filter(deleted_at__isnull=True)
        invoice_id = self.request.query_params.get("invoice_id")
        if invoice_id:
            qs = qs.filter(invoice__public_id=invoice_id)
        return qs

    def get_permissions(self):
        code = "invoice_lines.create" if self.request.method == "POST" else "invoice_lines.view"
        return [IsAuthenticated(), require_permission(code)()]

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except FinanceError as exc:
            return error_envelope(str(exc), status=409)

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        invoice = data.pop("invoice")
        serializer.instance = invoice_line_service.add_line(
            invoice=invoice, actor=self.request.user, **data
        )


class InvoiceLineDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = InvoiceLineSerializer

    def get_queryset(self):
        return InvoiceLine.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "invoice_lines.view",
            "PATCH": "invoice_lines.update",
            "DELETE": "invoice_lines.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except FinanceError as exc:
            return error_envelope(str(exc), status=409)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except FinanceError as exc:
            return error_envelope(str(exc), status=409)

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("invoice", None)
        invoice_line_service.update_line(line=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        invoice_line_service.remove_line(line=instance, actor=self.request.user)


class PaymentListCreateView(TenantListCreateAPIView):
    serializer_class = PaymentSerializer

    def get_queryset(self):
        qs = Payment.objects.filter(deleted_at__isnull=True)
        invoice_id = self.request.query_params.get("invoice_id")
        if invoice_id:
            qs = qs.filter(invoice__public_id=invoice_id)
        return qs

    def get_permissions(self):
        code = "payments.create" if self.request.method == "POST" else "payments.view"
        return [IsAuthenticated(), require_permission(code)()]

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except FinanceError as exc:
            return error_envelope(str(exc), status=409)

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        invoice = data.pop("invoice")
        serializer.instance = payment_service.record_payment(
            invoice=invoice, actor=self.request.user, **data
        )


class PaymentDetailView(TenantRetrieveAPIView):
    serializer_class = PaymentSerializer

    def get_queryset(self):
        return Payment.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("payments.view")()]


class RefundListCreateView(TenantListCreateAPIView):
    serializer_class = RefundSerializer

    def get_queryset(self):
        qs = Refund.objects.filter(deleted_at__isnull=True)
        payment_id = self.request.query_params.get("payment_id")
        if payment_id:
            qs = qs.filter(payment__public_id=payment_id)
        return qs

    def get_permissions(self):
        code = "refunds.create" if self.request.method == "POST" else "refunds.view"
        return [IsAuthenticated(), require_permission(code)()]

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except FinanceError as exc:
            return error_envelope(str(exc), status=409)

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        payment = data.pop("payment")
        serializer.instance = refund_service.issue_refund(
            payment=payment, actor=self.request.user, **data
        )


class RefundDetailView(TenantRetrieveAPIView):
    serializer_class = RefundSerializer

    def get_queryset(self):
        return Refund.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("refunds.view")()]


class ReceiptListView(TenantListAPIView):
    serializer_class = ReceiptSerializer

    def get_queryset(self):
        qs = Receipt.objects.filter(deleted_at__isnull=True)
        payment_id = self.request.query_params.get("payment_id")
        if payment_id:
            qs = qs.filter(payment__public_id=payment_id)
        return qs

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("receipts.view")()]


class ReceiptDetailView(TenantRetrieveAPIView):
    serializer_class = ReceiptSerializer

    def get_queryset(self):
        return Receipt.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("receipts.view")()]


class LedgerEntryListView(TenantListAPIView):
    serializer_class = LedgerEntrySerializer

    def get_queryset(self):
        qs = LedgerEntry.objects.all()
        school_id = self.request.query_params.get("school_id")
        ref_type = self.request.query_params.get("ref_type")
        ref_id = self.request.query_params.get("ref_id")
        if school_id:
            qs = qs.filter(school__public_id=school_id)
        if ref_type:
            qs = qs.filter(ref_type=ref_type)
        if ref_id:
            qs = qs.filter(ref_id=ref_id)
        return qs

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("ledger_entries.view")()]
